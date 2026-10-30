"""A frozen neural player, with control properties matched to the allied hunter."""
import config
from entities.ship import Ship
from hunter.neural.controller import NeuralController
from hunter.neural.policy import NeuralPolicy
from hunter.senses import Senses
from game_handlers.fire_rate_calculator import calculate_fire_cooldown


class MovementOnlyPolicy:
    """Keep the frozen recurrent movement policy, but force its trigger off."""
    def __init__(self, policy):
        self.policy = policy

    def initial_state(self):
        return self.policy.initial_state()

    def act(self, *args, **kwargs):
        (turn, thrust, _), state = self.policy.act(*args, **kwargs)
        return (turn, thrust, False), state


class HunterControlledShip(Ship):
    """Keep player collision, rendering and guns; match the neural pilot's flight tuning."""
    def __init__(self, position, settings):
        self.pilot_settings = settings
        self.movement = config.SETTINGS.hunterShip
        super().__init__(position)
        self.base_rotation_speed = self.movement.rotationSpeed*settings.turn_rate_multiplier

    @property
    def max_speed(self):
        return self.movement.maxSpeed

    @property
    def thrust_force(self):
        return self.movement.thrustForce*self.pilot_settings.thrust_multiplier

    @property
    def friction(self):
        return self.movement.friction


class PlayerSenses:
    def __init__(self, ship, settings):
        self.ship = ship
        self.health = settings.health
        self.fire_remaining = 0.
        self.fire_interval = .25
        self.burst_remaining = 0
        self._hit = None

    def __getattr__(self, name):
        return getattr(self.ship, name)


class FrozenNeuralPlayer:
    def __init__(self, ship, checkpoint, settings, decision_frames, firing_enabled=True):
        self.ship = ship
        self.view = PlayerSenses(ship, settings)
        self.senses = Senses(settings)
        policy = NeuralPolicy.load(checkpoint)
        self.controller = NeuralController(policy if firing_enabled else MovementOnlyPolicy(policy), decision_frames)

    def frame(self, world):
        def sense(last, now):
            return self.senses.observe(self.view, world.maze, world.roster.alive(),
                world.projectiles, [], world.hunter, last, now)
        action = self.controller.tick(sense)
        ship = self.ship
        ship.angle = (ship.angle+action.turn*ship.current_rotation_speed)%360
        if action.thrust:
            ship.apply_thrust()
        self.view.fire_remaining = max(0., self.view.fire_remaining-1/60)
        if action.fire and self.view.fire_remaining <= 0:
            world.projectiles.extend(ship.fire() or [])
            self.view.fire_interval = calculate_fire_cooldown(ship)/1000
            self.view.fire_remaining = self.view.fire_interval
        ship.update(1)
        ship.check_wall_collision(world.maze.walls,world.maze.spatial_grid)

    def close(self):
        self.controller.close()
