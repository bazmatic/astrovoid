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
_Avoid_: brain, agent, controller

**Hunter flight**:
One hunter in play with its pilot, from the moment it is summoned until it dies, is replaced, or the level ends.
_Avoid_: hunter session, hunter instance

**Surroundings**:
What the hunter may perceive at the moment it looks: the maze, the enemies, the threats, the pickups, and the player when the player can be seen.
_Avoid_: snapshot, world state, entities

### Things in the maze

**Jev beacon**:
A pickup that summons the hunter. Only the player collects it; the hunter never perceives it as a pickup.
_Avoid_: hunter powerup, summon crystal

**Threat**:
A projectile that can harm the hunter.
_Avoid_: bullet (when allegiance matters)

**Pickup**:
A powerup crystal the hunter may collect.
_Avoid_: item, loot

### Modes

**Duel**:
Two hunters with different pilots fight each other in a maze while the player watches.
_Avoid_: versus, arena match
