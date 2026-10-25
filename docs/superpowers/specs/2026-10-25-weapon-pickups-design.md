# Weapon pickups technical design

Date: 2026-10-25. Status: implemented initial version; tuning and explicitly marked proposals remain subject to playtesting.

## Agreed gameplay

Powerups become specific weapons. Touching a pickup immediately equips it, discarding the previous weapon and its remaining ammunition. Accidental pickups count. There is no inventory, equip button, confirmation, stacking, or upgrade level.

Weapons last until their ammunition runs out or another pickup replaces them. Running out returns the ship to an unlimited basic gun. Collecting the same weapon replaces its remaining ammunition with a fresh supply rather than adding ammunition.

These weapon-swap rules apply to the player. A hunter collecting any powerup keeps its existing gun and receives one generic timed power boost. It never equips the pickup's weapon or uses its ammo. The boost has the strength of the previous first upgrade (faster firing and larger/faster projectiles); another pickup only refreshes the timer. Use the existing `powerups.durationSeconds` setting. Historical replays retain their recorded stacking rules.

The first set is Twin Blaster, Scattergun, Railgun, Seeker, Grenade Launcher, and The Inflator. Each needs a recognisable pickup shape, projectile appearance, firing behaviour, and sound. Grenade explosions reuse the explosion system used by Belemnites.

Keep the recently implemented ground lifetime: weapon pickups remain for six seconds, fading over the last two. This ground lifetime never becomes an equipped-weapon timer. The earned Jev beacon remains a separate, persistent summon pickup.

## Proposed combat specification

Values here are starting points, not agreed balance requirements. One ammo unit buys one successful trigger action, including every projectile in that volley. No ammo is spent when the weapon cannot fire. Intervals use simulation time, expressed here in seconds.

| Weapon | Pickup silhouette / colour | Volley and behaviour | Ammo | Interval |
|---|---|---|---:|---:|
| Basic | No dropped pickup; neutral white bolt | One straight bolt, current base damage | Unlimited | Existing base interval |
| Twin Blaster | Two parallel bars / blue | Two parallel bolts from separate muzzle offsets; one hit each | 60 volleys | 0.14 s |
| Scattergun | Fan / orange | Five heavier, faster pellets across a 40-degree fan; two hits each | 20 volleys | 0.45 s |
| Railgun | Long needle / violet | Fast straight shot; two damage hits per target; pierces creatures and instantly destroys destructible walls; stopped by indestructible walls | 12 shots | 0.425 s |
| Seeker | Forked arrow / green | One guided missile; one hit; bounded turning rate; stops at walls | 18 missiles | 0.50 s |
| Grenade Launcher | Round shell with fuse / amber | One bouncing grenade; 1.2-second fuse; shared explosion at its final position | 10 grenades | 0.75 s |

Scattergun point-blank damage is intentionally high; range and cadence constrain it. Rail damage must use the existing enemy damage/trait path so armour, shields, splitting, deaths, and drops remain meaningful. Do not assume `Projectile.strength` is already a universal enemy-damage multiplier.

### Seeker targeting

Proposed initial rules: acquire the nearest visible hostile within a forward cone and a configured range, with stable entity order breaking ties. Use existing wall visibility checks. A missile turns at a bounded angular speed and maintains configured speed; it cannot turn instantly or pass through walls. Keep its target while valid. On loss or death, reacquire under the same rules; otherwise continue straight until collision or lifetime expiry. Allied shots never acquire friendly ships. Enemy shooters using the new system use their opposing allegiance as the target filter.

### Grenade motion and detonation

This is a top-down game. Proposed interpretation of an “arc”: planar travel with drag, a bouncing/spinning shell, and an optional visual hop/shadow. Do not add world-down gravity that bends every shot toward the bottom of the screen. Visual height does not allow passage over walls or enemies.

The grenade bounces from walls, boundaries, and rotating gates using collision normals. Reflect velocity with configurable restitution (start at 0.7), separate it from the surface, and continue consuming the remaining movement for that frame. Bound repeated collision resolution at corners. A bounce does not damage the wall; the eventual blast does.

An enemy within 28 pixels of the grenade (measured from the enemy hull) triggers detonation if visible from the trigger position. Test the swept flight path so near misses can trigger between frame endpoints. Walls and gates block proximity detection. Physical contact also detonates; the 1.2-second fuse remains the fallback. No extra direct-impact damage. The owner's body is ignored by projectile contact, but the explosion can hurt its owner and allies, matching Belemnite explosions. This makes close-range use dangerous. Friendly-fire and contact rules are proposed defaults, not additional user decisions.

The live grenade owns the moving fuse. On detonation, mark it inactive and enqueue one `Blast` at its current position with `fuse=0`. Never enqueue a stationary blast at launch and never run two independent fuses. Use a per-projectile detonation guard so simultaneous contact and fuse expiry cannot duplicate the blast.

Reuse `entities/explosion.py` (`Blast`, `Explosions`, `Fireball`, `reaches`, `push`) and `CollisionHandler.handle_blast`. `creatures/traits/combat.py::Explodes` is the existing Belemnite adapter to this machinery; a grenade constructs a `Blast` directly rather than pretending to be a creature.

Start with blast radius 60 px, `damage=2`, `push=6`, and `wall_hits=1`, all configurable. These are tuning proposals. Existing blast rules are radial and do not perform wall occlusion: preserving them means a grenade may hurt targets across a thin wall. Preserve damage to player/hunter as one ordinary blast hit, enemy damage as the configured number of hits, and the existing wall damage and chain attribution. Changing occlusion or friendly damage later should change the shared blast rules deliberately.

## Existing implementation and required seams

| Current location | Current responsibility | Required change |
|---|---|---|
| `entities/powerup_crystal.py` | Generic rotating gem, attraction, collection burst, six-second expiry | Become the weapon pickup; reuse a shared pickup lifecycle module |
| `entities/jev_beacon.py` | Persistent summon pickup, currently subclasses the crystal | Share pickup lifecycle without inheriting weapon state; retain formation and summon behaviour |
| `entities/ship.py` | Ammo stock, upgrade level/timer, volley creation, HUD | Delegate equipped weapon state and firing; show weapon and remaining ammo |
| `game_handlers/fire_rate_calculator.py` | Upgrade-level cadence calculation | Replace player weapon cadence lookup; retain legacy enemy cadence where needed |
| `creatures/traits/combat.py::Gun` | Creature/hunter firing and pickup upgrade events | Reuse the existing boost timer/firing path; cap new-mode pickup power at one and refresh its timer |
| `entities/projectile.py` | Straight projectile movement, rendering, consuming collisions | Preserve ordinary shots; add explicit specialised projectile behaviours |
| `creatures/encounter.py::Encounter.shoot` | Consumes a friendly shot on the first creature hit | Support ordered swept impacts and piercing without bypassing trait damage |
| `game_handlers/collision_handler.py` | Pickup distribution/collection, blast application, attribution | Equip pickup weapon; retain score/star events; dispatch projectile impacts correctly |
| `game.py` | Pickup update, firing/collision orchestration, level reset | Integrate shared firing state and projectile lifecycle; reset on new level |
| `policies/ammo.py` and level configuration | Limited/unlimited player ammo policies | Migrate new weapon rules explicitly, as described below |
| `hunter/senses.py`, `experiments/rollout.py` | Upgrade observation and upgrade-related rewards/metrics | Version boost/lifetime observations; retain boost-duration rewards and metrics |

## Proposed module interface

Introduce `weapons/` with a small immutable definition registry, equipped state, and firing behaviour. Definitions hold stable IDs, ammo capacity, cooldown, projectile tuning, and presentation IDs. Load and validate tuning once; never read settings files inside a firing loop.

```python
WeaponId = str  # Stable registered identifier; validated at configuration/load seams.

@dataclass(frozen=True)
class WeaponDefinition:
    id: WeaponId
    ammo_capacity: int | None  # None only for basic
    cooldown_frames: float
    # Typed projectile/presentation configuration, validated on load.

class EquippedWeapon:
    def __init__(self, catalog: WeaponCatalog): ...
    def equip(self, weapon_id: WeaponId) -> None: ...
    def update(self, dt: float) -> None: ...
    def try_fire(self, context: FireContext) -> FireResult: ...
    def reset(self) -> None: ...
    @property
    def view(self) -> WeaponView: ...  # Immutable ID, ammo/capacity, cooldown, aim profile.
```

`FireContext` supplies only muzzle pose and launch attribution. Targeting access belongs to guided-projectile updates, not to every weapon's firing interface. `FireResult` contains emitted projectiles and the launch weapon identity for sound/events, including when the final volley has already returned equipped state to basic. A not-ready result contains no projectiles and no firing event. The firing module does not mutate scoring, render the HUD, or call global game objects. The player owns an equipped-state instance. Hunters keep their existing gun and boost state in the creature Gun trait; no weapon inventory or ammo state is added to hunters.

`WeaponCatalog` supplies validated definitions and volley factories. Definitions and factories are injected at construction, rather than discovered through global config inside `EquippedWeapon`. Basic, twin, and scatter use one configurable bolt-volley factory (muzzle offsets, angle offsets, range); rail, seeker, and grenade select their distinct projectile behaviours. Adding a weapon with existing behaviour requires a definition and registration, not edits to a central weapon-ID switch.

`WeaponView` is the read-only interface for HUD, fire-control adapters, and observations. These callers do not inspect projectile internals or mutate equipped state. Normalised ammo is derived from the same state and capacity; no second mutable HUD or training ammo counter is maintained.

Invariants:

- Basic has unlimited ammo; every special weapon has an integer count between zero and its capacity.
- Equipping replaces state atomically; no dropped copy of the old weapon is created.
- Existing shots keep their launch weapon, source, and behaviour after a swap, death, or ammo depletion.
- A valid volley is created before consuming exactly one ammo unit. Failed firing leaves ammo unchanged.
- The final special volley is emitted normally, then equipped state returns to basic. Preserve that volley's cooldown before basic can fire.
- Proposed swap rule: retain the current remaining cooldown. Touching pickups cannot bypass firing cadence; equipping while ready permits immediate fire.
- New level, restart, and respawn start with basic. No persistence across levels in the first implementation.
- Pausing freezes cooldowns, ground expiry, projectile lifetimes, and grenade fuses.

Convert milliseconds to simulation frames at the boundary where necessary. The player weapon state authorises player shots; the existing hunter burst scheduler authorises hunter shots. Do not layer the old upgrade cooldown and the new weapon cooldown on top of one another.

### Responsibility ownership (DRY and SOLID)

| Module | Sole responsibility and dependencies |
|---|---|
| Weapon catalog | Authoritative weapon definitions, presentation IDs, and factory registration; validates capacities, timing, behaviour settings, and duplicate/unknown IDs |
| Equipped state | Player equip, ammo, cooldown, fallback, and successful volley transitions; depends on the injected catalog |
| Hunter Gun trait | Existing gun, fixed generic boost strength, boost timer refresh/expiry, and existing burst cadence |
| Pickup lifecycle | Age, attraction, availability, fade, and collection animation; accepts finite or persistent lifetime and never assumes a weapon payload |
| Pickup collection | Resolve eligible collector and consume once; dispatch player weapon equip, hunter generic boost, or beacon summon; preserve existing collector-specific score/star rules |
| Projectile simulation | Movement, guidance, fuse, and physical contact response; consumes collision queries and returns hit/blast requests |
| Target-hit application | Apply damage through creature traits, hit accounting, deaths, and drops; shared by direct shots, rails, and blast damage |
| Explosion system | Blast queue, existing area-damage application, wall damage, knockback, chain reactions, and fireball presentation |
| Presentation / training adapters | Read immutable state and combat events; translate them into HUD, audio, observations, metrics, or rewards |

Extract pickup lifecycle before making crystals weapon-specific. Weapon pickups and beacons compose that module (or are sibling implementations of a small pickup interface). A beacon must not need a dummy weapon ID, infinite weapon capacity, or an override that disables inherited equip behaviour. Keep beacon formation eligibility in its own implementation. Collection orchestration is the sole owner of the transition from available to consumed; both payloads obey the same consume-once contract.

Keep physics query interfaces non-mutating. Bolt, rail, missile, and grenade are interchangeable through a projectile lifecycle interface, but each owns its contact response: consume, pierce, or bounce/detonate. Consumers must not depend on every projectile deactivating on contact. Retain the existing consuming collision methods only behind legacy adapters, rather than requiring a rail to violate their contract.

Use narrow dependency interfaces where behaviour actually varies: collision queries provide ordered contacts; a targeting adapter provides eligible visible targets to seekers; a damage adapter applies a hit. None exposes the whole `Game`, mutable roster, HUD, or scorer. Reuse existing geometry and visibility helpers behind these interfaces. Add no generic plugin framework or per-weapon class where definition data is sufficient.

One simulation owner ticks each player equipped state, hunter boost timer, and projectile once per step and dispatches returned events once. A grenade's in-flight fuse, a pickup's ground lifetime, and a queued Belemnite blast's fuse are separate lifecycles, each with exactly one clock owner. Shared units and timer helpers are appropriate; sharing mutable timers is not.

## Projectile collision contract

Add explicit behaviour by composition or small subclasses: ordinary bolt, piercing rail, guided missile, and grenade. Avoid a growing matrix of unrelated Boolean flags on `Projectile`.

New fast shots need swept segment/circle and segment/wall tests. Resolve earliest time of impact, with stable ordering for ties; a target behind a wall cannot be hit first merely because it appears earlier in the roster. Moving gates must participate through their existing collision representation. Use substeps or relative-motion checks where gate motion requires them.

A rail processes impacts in travel order, tracks creature identities already hit, and applies its configured damage once per creature over its whole life. It may hit several creatures in one update. Destroy each destructible block instantly through the shared maze damage operation, regardless of its hit points, and continue with unchanged speed and remaining travel. Refresh collision surfaces after destruction so newly exposed adjoining blocks are also sliced. Indestructible walls and gates stop the shot. Split children are distinct targets, but prevent newly spawned children from taking additional hits in the same impact traversal by snapshotting candidate identities for that step.

Extract a target-hit operation from `Encounter.shoot` that preserves traits, hit counters, death handling, drops, and kill source. It accepts an immutable hit request with target identity, damage hits, momentum, and launch attribution; it does not query physical contact or consume projectiles. Direct shots, rails, and the existing blast adapter invoke this same operation. Multi-hit damage repeats the existing trait-aware hit semantics while the target remains active; do not create a separate direct-health subtraction path. Keep the old consuming adapter for existing projectiles. Separate physical contact queries from decisions to consume a shot: the current `check_circle_collision` deactivates the projectile immediately, which cannot implement piercing or grenade bounce correctly.

Use `dt` for new projectile timers; existing `Projectile.update` currently subtracts one lifetime unit per update regardless of `dt`. Change existing projectile timing only with explicit regression coverage rather than accidentally bundling it into the feature.

## Pickups, distribution, and presentation

Weapon identity is assigned when the pickup spawns, using the seeded simulation RNG. Rendering never rerolls it. Proposed initial distribution is equal probability across the six specials; expose validated weights and optional level allowlists for later balancing. Preserve existing drop chance and earned-beacon eligibility. Resolve the beacon-versus-weapon drop first, then choose a weapon only if a weapon pickup is actually spawned.

The drop selector receives an RNG dependency and the validated catalog/distribution, rather than creating or reseeding an RNG. IDs, capacities, symbols, sounds, and drop eligibility come from the catalog; adapters must not maintain parallel weapon lists. Observation feature order is frozen and versioned independently of catalog iteration order. Hunters observe generic boost state and pickup lifetime; adding a player weapon does not change their feature layout.

Keep automatic attraction to the nearest friendly and physical-touch collection. Therefore attraction can also pull an unwanted weapon toward a ship. Keep the current player-first resolution if both friendlies touch the same pickup in one frame. A successful player collection equips once; a hunter collection refreshes its generic boost once. Preserve the respective existing pickup score/star events exactly once. Expiry records no collection. Multiple pickups collected in a frame resolve in stable list order, with the last collected weapon equipped; no preference logic silently protects the current weapon.

Use both silhouette and colour. Keep the existing spawn pop, glow, trail, fade, and collection burst, with weapon-specific symbols and colours. Show equipped name/icon and integer ammo in the HUD; basic shows infinity. Remove `GUN UPGRADE xN` and its duration bar. Show a brief equip notice and distinct firing sounds without an extra interaction or modal.

## Ammo and level-policy migration

The unlimited basic gun is an explicit change from today's finite player ammo stock. For the new ruleset, level `limited` and `unlimited` ammo policies must not make basic finite or specials infinite. Specials always consume their own capacity; kills and pickups no longer refill a shared gun-ammo pool. Remove player timed upgrades and per-kill upgrade/refill side effects wherever active. Keep the hunter generic boost timer.

Audit every use of `ship.ammo`, `INITIAL_AMMO`, `POWERUP_AMMO_REFILL`, upgrade duration, fire-rate upgrades, and ammo-based failure checks. Determine whether any “power” meter also serves movement or survival before migrating it: those costs are separate from weapon ammo and must not be deleted just because they share a field today. New weapon-ammo depletion must never end a level; it equips basic.

Keep legacy policy parsing for old levels and historical runs, but make new gameplay semantics explicit through a combat ruleset version. Deprecate obsolete ammo options in the level editor for new rules rather than silently offering controls that do nothing. Level JSON need not be rewritten solely to assign random weapon drops; add allowlists only where authored progression warrants them.

Select the legacy or weapon-pickup combat adapter once when constructing a session. Keep old ammo/upgrade interpretation inside the legacy adapter, with the same launch/result interfaces where practical. Avoid scattered `if legacy` checks in weapons, HUD, pilots, and collision code. Reuse the verified blast and trait-damage modules in both modes. Record the supported legacy version explicitly; do not build a general historical engine framework. If exact replay requires an older executable, report that limitation rather than treating metadata alone as compatibility.

## Hunters, training, and deterministic replay

The player equips weapon pickups. Hunters, including Rules, Jev, and Neural pilots, keep their existing gun and movement/fire action interfaces. Any collected powerup activates a generic first-level boost, independent of the pickup's weapon identity. Strength never stacks: repeated collection sets the level to one and restarts `powerups.durationSeconds`. Expiry restores the unboosted gun. No equip action, special-weapon ammunition, or weapon-selection feature is added to hunter pilots. Enemy creatures retain their authored guns; a pickup-capable hunter follows the same generic-boost contract regardless of pilot type.

Reuse the existing `Gun` trait's upgrade timer, first-level projectile styling, and burst cadence rather than creating a second boost module. New-session mode caps the level at one; legacy replay mode retains historical incrementing levels. Existing boost visuals and pickup events continue to work. Fire control in the new mode accounts for boosted projectile speed.

Append explicit `power_boost` and normalised `power_boost_remaining` observations, plus visible/remembered pickup lifetime. Keep existing geometry and scalar upgrade feature ordering. Pickup identity does not affect a hunter's boost and is therefore omitted from its observation schema.

Version observation schema, combat ruleset, weapon tuning, and pickup distribution in run metadata. Resume and replay reconstruct the recorded values. Old checkpoints use an explicit legacy-prefix adapter; matching dimensions alone does not establish compatibility. The added boost timer can be learned with further training.

Keep `upgrade_bonus` and `upgraded_fraction` as the hunter boost-duration reward and metric. Label them “Hunter power boost” in the dashboard. Keep pickup counts and score/star accounting. Player weapon statistics and delayed grenade-chain kills retain launch weapon identity and player/hunter source attribution.

Stable target ordering, seeded pickup selection, and simulation-time fuses are required for replay. Existing explosion effects and centre-point knockback use randomness: preserve deterministic simulation seeding and update order, and avoid adding rendering-driven random consumption. Historical runs need their original combat semantics, not just their old observation vector.

## Implementation sequence

1. Add ruleset/version metadata and definition validation; implement equipped state and transition tests.
2. Introduce shared firing for basic, Twin Blaster, and Scattergun; connect player state and cap hunter generic boosts without changing ordinary enemy guns.
3. Extract collision/hit seams; add swept rail impacts, guided missiles, and bouncing grenade motion. Connect grenade detonation to shared blasts.
4. Add weapon-bearing pickups, seeded distribution, collection accounting, icons, HUD, and sounds; retain beacon lifecycle and ground fade.
5. Migrate ammo policies and any shared energy accounting deliberately; remove player upgrade/refill paths and retain the hunter generic boost timer. Update boosted hunter fire-control inputs.
6. Add observation/reward versions, run metadata, replay/resume handling, and editor/config validation. Playtest balance before setting final defaults.

Each intermediate change should remain runnable behind the ruleset selection. Enable the complete new ruleset for normal play when all six weapons, HUD, and lifecycle rules are integrated.

## Validation and acceptance

- Player state transitions: replacement discards ammo; same-weapon pickup resets capacity; final volley fires then falls back; cooldown survives replacement/depletion; basic never runs dry.
- Hunter boost: every pickup type gives the same level-one boost; subsequent pickups refresh duration without stacking or equipping a weapon; expiry restores normal firing; score/star/events remain correct.
- Pickup lifecycle: automatic collection, attraction, stable simultaneous collection, player/hunter ownership, six-second expiry, collectible while fading, no expiry reward, permanent beacon.
- Combat: twin muzzle geometry; scatter spread/range; rail ordered hits, once-per-target damage, instant rock destruction through adjoining blocks, and indestructible-wall blocking; seeker turn bound, allegiance, loss/reacquisition, and wall-blocked acquisition.
- Grenades: wall/gate/corner bounces, fuse across different `dt`, pause, contact-plus-expiry single detonation, no duplicate impact damage, source retained after replacement/death, self/allied blast damage, wall damage, and Belemnite chain attribution.
- Integration: trait-based armour/shields and split deaths, scoring/stars, no per-kill upgrades, level restart, HUD infinity/ammo, enemy guns unchanged, active grenades handled consistently at level completion under existing pending-explosion rules.
- Training: observation names/order/version validation, no silent legacy reinterpretation, fresh-training smoke test for every weapon, deterministic replay/resume from recorded rules and tuning.
- Visual/audio checks: distinguish all six pickups at gameplay scale without relying on colour; inspect full/fading states, projectile identity, equip notice, rail readability, seeker motion, grenade fuse cue, and shared explosion effects.
- Performance: measure dense scatter volleys, many seekers, piercing through crowds, and grenade/Belemnite chains. Bound collision substeps and targeting work without truncating authoritative damage.
- Module contracts: test player equipped-state transitions and hunter generic-boost refresh/expiry separately and common projectile lifecycle tests for bolt/rail/missile/grenade. Verify pickup lifecycle for both weapon and beacon payloads. Test shared target-hit application against shields, armour, splits, and blasts. Register a test-only definition using an existing factory and verify equip/fire/presentation lookup without editing dispatch logic. Use injected collision/target/RNG adapters for focused tests; retain end-to-end checks for actual geometry and accounting.

## Decisions to confirm through playtesting

Ammo budgets, cadence, damage, range, grenade blast size and self-damage feel; equal drop weights; grenade contact detonation; cooldown retention on pickup; level-reset behaviour; and whether weapon availability should be introduced gradually across the campaign. None of these tuning proposals changes the agreed automatic replacement and finite-ammo foundation.


## Implementation notes (2026-10-25)

The implementation lives in `weapons/catalog.py`, `state.py`, `projectile.py`, `simulation.py`, `geometry.py`, and `presentation.py`. The catalog contains validated immutable tuning and drop weights; `EquippedWeapon` owns player ammo, replacement, fallback, and cadence. The existing hunter `Gun` trait owns its generic boost timer and firing. Its concrete firing interface is `try_fire(pos, angle, source)`, returning an immutable `FireResult`, with read-only `WeaponView` for consumers. Registered projectile classes implement guidance, target/surface contact, and fuse behaviour; the shared simulator orders non-mutating swept contacts. Existing creature traits remain the shared damage path.

`Pickup` now supplies lifecycle for sibling `PowerupCrystal` and `JevBeacon` implementations. Weapon symbols, colour, ammo, and equip notices are connected to gameplay. A level may supply a non-empty `weapons` list of special weapon IDs to restrict random drops. Tuning is currently edited in the Python catalog, not a new dashboard editor.

Normal play and new PPO runs use `weapon-pickups-v1`. Historical episode calls default to `legacy`; run metadata records combat rules, tuning (including resolved base projectile speed/radius), and observation version. Resume selects recorded combat semantics and explicitly expands the previous observation prefix and its Adam moment buffers. Older neural policies use a zero-weight adapter for added boost timer/lifetime features; further training can teach the new observations. Compatibility is integrated at existing ship/gun/session entrypoints rather than introducing a second whole-game engine.

Training retains the `upgrade_bonus` reward and `upgraded_fraction` chart for generic hunter power boosts, labelled accordingly. No special-weapon reward is needed for hunters. Player weapon pickups and kills are counted by weapon, and grenade chains retain launch weapon and source attribution.

Grenades use planar drag and spin, visibility-gated proximity/contact detonation, wall/gate bounces, and the existing radial blast rules including friendly damage and wall penetration. They do not fly over cover. Gates are queried at their current frame pose with their physical thickness; exact continuous rotational collision is not implemented. Exiting discards in-flight grenades with the other projectiles; already queued blasts retain the game's existing explosion lifecycle.

## Weapon feel tuning

Railgun interval is 25.5 simulation frames (0.425 s), twice its previous firing rate. Scattergun interval is 27 frames (0.45 s); each of its five pellets now deals two damage hits, travels 15% faster, and has a larger visible radius. Its sound adds a deeper low-frequency body without simulation randomness. Grenade proximity radius is 28 px from the enemy hull, with wall/gate visibility checks at the swept trigger position. Proximity is part of the projectile contact interface, preserving the shared ordered collision simulation and single-detonation guard.

New tuning fields default to zero for older recorded weapon snapshots, preserving their previous fuse/contact behaviour and audio body.

## The Inflator

Sixth pickup: a pink balloon icon and bubble projectile, 18 shots, 0.5-second cadence. The initial hit inflates without applying ordinary damage. Any subsequent projectile hit (including another inflation shot) or blast kills the target immediately through normal Encounter kill accounting, death traits, splits, drops, and source attribution. Expiry preserves the creature's underlying health and smoothly shrinks the final quarter-second back to normal size.

`powerups.inflationDurationSeconds` defaults to 5 and `inflationSizeMultiplier` defaults to 5 in `config/settings.json`. These resolve into validated per-weapon tuning and are recorded in run snapshots. Older recorded catalogs have no Inflator drop and remain unchanged.

The `creatures/inflation.py` module owns effect duration, size, and next-hit vulnerability. Encounter invokes its hit hook and advances it once per creature step. Creature presentation and projectile/blast targeting use the enlarged outline; navigation retains its ordinary radius to avoid forcing giant creatures into walls. Drawing restores the physical radius even if a body raises an error. Neural enemy hit-point observations report the effective one-hit vulnerability without changing feature layout. Hunters collecting the pickup receive their existing generic power boost.
