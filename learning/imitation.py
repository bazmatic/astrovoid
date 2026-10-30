"""Balanced recurrent demonstrations, independent of creatures and game state."""
import numpy as np


class Demonstrations:
    def __init__(self, episodes, head_names, selected_heads, focus_head=None):
        import torch
        self.names = tuple(head_names)
        self.heads = tuple(selected_heads)
        self.indices = {name:i for i,name in enumerate(self.names)}
        self.episodes = []
        for e in episodes:
            self.episodes.append(dict(
                x=torch.as_tensor(np.asarray(e['x']),dtype=torch.float32).unsqueeze(0),
                critic=torch.as_tensor(np.asarray(e['critic']),dtype=torch.float32).unsqueeze(0),
                actions=torch.as_tensor(np.asarray(e['actions']),dtype=torch.float32),
                alive=torch.as_tensor(e['alive'],dtype=torch.bool),
                enabled=torch.as_tensor(np.asarray(e['enabled']),dtype=torch.bool),
                legal={k:torch.as_tensor(np.asarray(v),dtype=torch.bool) for k,v in e.get('legal',{}).items()}))
        self.focus = [i for i,e in enumerate(self.episodes) if focus_head is not None
                      and (e['alive'] & e['enabled'][:,self.indices[focus_head]]).any()]

    def weights(self, indices, heads, continuous=()):
        """Each observed class has equal total weight across the selected trajectories."""
        import torch
        weights={}
        for name in heads:
            labels=[];column=self.indices[name]
            for i in indices:
                e=self.episodes[i];active=e['alive'] & e['enabled'][:,column]
                labels.append(e['actions'][active,column])
            labels=torch.cat(labels)
            if not labels.numel():continue
            if name in continuous:
                weights[name]=1/labels.numel()
                continue
            counts=torch.bincount(labels.long()).float()
            weights[name]=1/(counts.clamp_min(1)*(counts>0).sum())
        return weights

    def loss(self, net, indices, heads=None, weights=None):
        import torch
        heads=tuple(heads or self.heads)
        weights=self.weights(indices,heads,getattr(net,'continuous',())) if weights is None else weights
        total=next(net.parameters()).sum()*0
        for i in indices:
            e=self.episodes[i];logits,_=net(e['x'],e['critic'])
            for name in heads:
                if name not in weights:continue
                column=self.indices[name];active=e['alive'] & e['enabled'][:,column]
                if not active.any():continue
                z=logits[name][0][active]
                if name in getattr(net,'continuous',()):
                    labels=e['actions'][active,column]
                    total=total+(z[:,0].tanh()-labels.tanh()).square().sum()*weights[name]/max(1,len(weights))
                    continue
                if name in e['legal']:z=z.masked_fill(~e['legal'][name][active],-1e9)
                labels=e['actions'][active,column].long()
                ce=torch.nn.functional.cross_entropy(z,labels,reduction='none')
                total=total+(ce*weights[name][labels]).sum()/max(1,len(weights))
        return total

    def rehearse(self, net, rng, heads):
        if not self.episodes:return next(net.parameters()).sum()*0
        # Keep a rare event trajectory in each rehearsal, alongside an ordinary example.
        first=int(rng.choice(self.focus)) if self.focus else int(rng.integers(len(self.episodes)))
        second=int(rng.integers(len(self.episodes)))
        return self.loss(net,list(dict.fromkeys((first,second))),heads=heads)

    def fit(self, net, epochs=64, lr=1e-3):
        import torch
        optimiser=torch.optim.Adam(net.parameters(),lr=lr)
        indices=list(range(len(self.episodes)))
        if not indices:return
        weights=self.weights(indices,self.heads,getattr(net,'continuous',()))
        for _ in range(epochs):
            optimiser.zero_grad()
            # Accumulate a globally balanced gradient; negative-only episodes cannot
            # cancel the weighting by normalising their own cross entropy separately.
            for i in indices:self.loss(net,[i],weights=weights).backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(),1)
            optimiser.step()
