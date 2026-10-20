# ASTRO VOID

A momentum-based space shooter: the player flies a ship through procedurally generated mazes full of enemies, and can call in an allied ship to help.

## Language

### Ships

**Player**:
The human-flown ship.
_Avoid_: user, ship (on its own, when the hunter is also present)

**Hunter**:
The allied ship that flies itself, summoned by collecting a Jev beacon. Its kills do not score for the player.
_Avoid_: ally ship, bot, AI ship

**Pilot**:
Whatever decides how the hunter turns, thrusts and fires. One of three: Jev (a remote model), rules (the same criteria written as plain code), or neural (a small trained policy).
_Avoid_: agent, controller; "brain" is the wider term for whatever decides a Creature's controls

**Hunter flight**:
One hunter in play with its pilot, from the moment it is summoned until it dies, is replaced, or the level ends.
_Avoid_: hunter session, hunter instance

**Surroundings**:
What the hunter may perceive at the moment it looks: the maze, the enemies, the threats, the pickups, and the player when the player can be seen.
_Avoid_: snapshot, world state, entities

### Things in the maze

**Strong wall**:
A wall block that no shot can destroy, drawn as riveted metal plate. Only hand-made layouts have them.
_Avoid_: steel wall, indestructible block, rim (the outer ring is a different thing)

**Jev beacon**:
A pickup that summons the hunter. Only the player collects it; the hunter never perceives it as a pickup.
_Avoid_: hunter powerup, summon crystal

**Threat**:
A projectile that can harm the hunter.
_Avoid_: bullet (when allegiance matters)

**Pickup**:
A powerup crystal the hunter may collect.
_Avoid_: item, loot

### Enemies

**Roster**:
Every enemy on the level, of every kind, alive or dying, until the level is cleared.
_Avoid_: entity manager, enemy lists

**Enemy Kind**:
One kind of enemy as `config/enemies.json` describes it: its code name, the names the player reads, how it behaves in
the maze (anchored, replays the player, its par allowance, the room it needs) and its own tuning. Every kind can be
placed in a level.
_Avoid_: enemy type (in new code; level files still say "type")

The names the player reads. The friendly hunter keeps its own names ("Rules hunter", "Neural hunter"); these are for enemies only.

**Urchin**:
An enemy that sits still. Shots shove it, and it takes several hits.
_Code name_: static

**Crab**:
An enemy that moves back and forth.
_Code name_: patrol

**Jelly**:
An enemy that chases the player.
_Code name_: aggressive

**Squiddler**:
An enemy that flies the player's own recorded moves.
_Code name_: replay

**Flocker**:
An enemy that moves in a flock.
_Code name_: flocker

**Flighthouse**:
The flighthouse enemy.
_Code name_: flighthouse

**Egg**:
An enemy that hatches into squidlets.
_Code name_: egg

**Squidlet**:
An enemy hatched from an egg, or placed in a level.
_Code name_: baby

**Anemone**:
The anemone enemy.
_Code name_: anemone

**Squiddler Boss**:
A boss that splits when hit.
_Code name_: split_boss

**Mother**:
A boss that lays eggs.
_Code name_: mother_boss

**Terminator**:
An enemy ship flown by the rules pilot.
_Code name_: rules_hunter

**Viber**:
An enemy ship flown by the neural pilot.
_Code name_: neural_hunter

**Boss Viber**:
A Viber at double the size that takes double the hits.
_Code name_: boss_viber

**Vibelet**:
A Viber at half the size that one hit destroys; its shots are almost harmless.
_Code name_: vibelet

**Belemnite**:
A spiky squid in a pointed shell that chases the player as a Jelly does. It has no guns; when it dies it explodes, hurting everything near it, other enemies too, so one can set off the next.
_Code name_: belemnite

**Blast**:
An explosion's reach and what it does to everything inside it: the player, the hunter, enemies and wall blocks. A blast set off by another counts its kills for whoever lit the first.
_Avoid_: explosion (that is what the player sees of it), splash damage

### Creatures

How an enemy is built when its catalogue entry names a `body` (the Urchin, Crab, Jelly and Belemnite so far).

**Creature**:
One enemy assembled from its Enemy Kind's catalogue entry: a Body and a list of Traits. It holds what every enemy has
(position, velocity, hit points, allegiance) and the state its traits keep.
_Avoid_: enemy class, entity (for this sense)

**Body**:
How a creature looks: it animates and draws the creature, and plays its death. It never decides what the creature does.
_Avoid_: sprite, skin, renderer

**Trait**:
One piece of a creature's behaviour, named and configured in its catalogue entry; its traits run in the entry's order.
_Avoid_: component, behaviour, strategy

**Brain**:
A Trait that decides a creature's controls each frame: where it heads and when it fires (chase, patrol, still).
_Avoid_: AI, strategy

**Propulsion**:
A Trait that turns a creature's controls into motion (drift steers toward a heading; coasts only keeps its momentum).
_Avoid_: movement strategy, engine

**Encounter**:
What happens to the creatures on a level in one frame: it runs their traits in roster order, offers each friendly shot
to them, and gives traits the ship, the hunter, the maze and the rest of what they act on.
_Avoid_: enemy updater, world, scene

### Modes

**Duel**:
Two hunters with different pilots fight each other in a maze while the player watches.
_Avoid_: versus, arena match
