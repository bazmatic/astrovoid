"""Game configuration loader that exposes typed settings backed by JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


def _as_color(value: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(value)


@dataclass
class ScreenSettings:
    width: int
    height: int
    fps: int
    fullscreen: bool


@dataclass
class ShipSettings:
    size: int
    rotationSpeed: float
    thrustForce: float
    friction: float
    maxSpeed: float
    spawnOffset: float
    collisionRestitution: float


@dataclass
class ResourceSettings:
    initialFuel: int
    initialAmmo: int
    fuelPerThrust: int
    ammoPerShot: int
    shieldFuelPerFrame: int


@dataclass
class ScoringSettings:
    maxLevelScore: int
    timePenaltyRate: int
    collisionPenalty: int
    ammoPenaltyRate: float
    fuelPenaltyRate: float
    wallCollisionPenalty: int
    powerupCrystalBonus: int
    enemyBulletPenalty: int


@dataclass
class DifficultySettings:
    baseMazeSize: int
    mazeSizeIncrement: int
    maxMazeSize: int
    baseEnemyCount: int
    enemyCountIncrement: int
    tutorialLevels: int


@dataclass
class MazeComplexityPreset:
    stepSize: int
    passageWidth: int
    clearRadius: int
    cornerClearSize: int
    extraPathsMultiplier: int
    gridSizeBase: int
    gridSizeIncrement: int


@dataclass
class MazeSettings:
    wallThickness: int
    cellSize: Optional[int]
    minPassageWidth: int
    wallHitPoints: int
    shipSpawnOffset: float
    complexityPresets: Dict[str, MazeComplexityPreset]


@dataclass
class EnemySettings:
    staticSize: int
    dynamicSize: int
    patrolSpeed: float
    aggressiveSpeed: float
    damage: int
    stuckDetectionThreshold: float
    shiftAngleMin: int
    shiftAngleMax: int
    shiftDurationMin: int
    shiftDurationMax: int
    fireIntervalMin: int
    fireIntervalMax: int
    fireRange: float
    replayFireAngleTolerance: float


@dataclass
class ReplayEnemySettings:
    windowSize: int
    size: int
    color: Tuple[int, int, int]
    baseCount: int
    scaleFactor: float


@dataclass
class BabySettings:
    size: int
    speedMultiplier: float


@dataclass
class SplitBossSettings:
    sizeMultiplier: float
    hitPoints: int
    spawnOffsetRange: int
    splitVelocityMagnitude: float
    baseCount: int
    scaleFactor: float
    childrenCount: int


@dataclass
class MotherBossSettings:
    sizeMultiplier: float
    hitPoints: int
    eggLayInterval: int
    baseCount: int
    scaleFactor: float
    lineGlowIntensityMax: float
    blinkFrequencyMultiplierMax: float
    blinkDurationMultiplierMax: float
    projectileSpeedMultiplier: float
    projectileImpactMultiplier: float
    projectileGlowColor: Tuple[int, int, int]
    projectileGlowRadiusMultiplier: float
    projectileGlowIntensity: float


@dataclass
class EggSettings:
    initialSize: int
    maxSize: int
    growthRateMin: float
    growthRateMax: float
    spawnOffsetRange: int
    baseCount: int
    scaleFactor: float
    color: Tuple[int, int, int]
    hitPoints: int
    babySpawnMin: int
    babySpawnMax: int


@dataclass
class MomentumSettings:
    staticEnemyHitPoints: int
    transferFactor: float
    frictionCoefficient: float
    minVelocityThreshold: float


@dataclass
class ProjectileSettings:
    speed: float
    size: int
    lifetime: int
    color: Tuple[int, int, int]
    impactForce: float


@dataclass
class VisualSettings:
    shipGlowIntensity: float
    shipGlowRadiusMultiplier: float
    enemyPulseSpeed: float
    enemyPulseAmplitude: float
    thrustPlumeLength: int
    thrustPlumeParticles: int


@dataclass
class ColorsSettings:
    background: Tuple[int, int, int]
    ship: Tuple[int, int, int]
    walls: Tuple[int, int, int]
    enemyStatic: Tuple[int, int, int]
    enemyDynamic: Tuple[int, int, int]
    projectile: Tuple[int, int, int]
    exit: Tuple[int, int, int]
    start: Tuple[int, int, int]
    text: Tuple[int, int, int]
    uiBackground: Tuple[int, int, int]
    shipNose: Tuple[int, int, int]
    shipRear: Tuple[int, int, int]
    shipDamagedNose: Tuple[int, int, int]
    shipDamagedRear: Tuple[int, int, int]


@dataclass
class ExitPortalSettings:
    attractionRadius: int
    attractionForceMultiplier: float
    glowMultiplier: float
    glowLayerOffset: int


@dataclass
class SoundSettings:
    enabled: bool
    sampleRate: int
    thrusterVolume: float
    shootVolume: float
    enemyDestroyVolume: float
    exitWarbleVolume: float
    powerupActivationVolume: float
    thrusterNoiseDuration: float
    shootBlipFrequency: int
    shootBlipDuration: float
    hitSoundVolume: float


@dataclass
class ControllerSettings:
    deadzone: float
    triggerThreshold: float


@dataclass
class PowerupFireRateMultipliers:
    level1: float
    level2: float
    level3: float


@dataclass
class PowerupUpgradedProjectile:
    spreadAngle: float
    sizeMultiplier: float
    speedMultiplier: float
    color: Tuple[int, int, int]
    glowColor: Tuple[int, int, int]


@dataclass
class PowerupBeyondLevel3:
    sizeIncrement: float
    speedIncrement: float
    glowIntensityIncrement: float
    hueRotation: float


@dataclass
class PowerupSettings:
    crystalSize: int
    crystalSpawnChance: float
    crystalRotationSpeed: float
    crystalGlowIntensity: float
    crystalColor: Tuple[int, int, int]
    attractionRadius: int
    attractionSpeed: float
    flashDurationFrames: int
    flashTintStrength: float
    flashGlowMultiplier: float
    fireRateBaseCooldown: int
    fireRateMultipliers: PowerupFireRateMultipliers
    upgradedProjectile: PowerupUpgradedProjectile
    beyondLevel3: PowerupBeyondLevel3
    rotationSpeedMultiplier: float


@dataclass
class StarAnimationSettings:
    appearDuration: float
    twinkleSpeed: float
    twinkleIntensity: float
    tinkleBasePitch: int
    tinklePitchIncrement: int
    levelCompleteStarSize: int


@dataclass
class UIAnimations:
    neonGlowIntensity: float
    neonGlowPulseSpeed: float
    buttonGlowIntensity: float
    buttonGlowPulseSpeed: float


@dataclass
class UIStarfield:
    starCount: int
    twinkleSpeed: float


@dataclass
class UIFonts:
    title: int
    subtitle: int
    button: int
    hint: int


@dataclass
class UISettings:
    splashDisplayDuration: float
    splashFadeInDuration: float
    splashFadeOutDuration: float
    neonAsterStart: Tuple[int, int, int]
    neonAsterEnd: Tuple[int, int, int]
    neonVoidStart: Tuple[int, int, int]
    neonVoidEnd: Tuple[int, int, int]
    buttonAColor: Tuple[int, int, int]
    buttonBColor: Tuple[int, int, int]
    buttonGlowColor: Tuple[int, int, int]
    animations: UIAnimations
    starfield: UIStarfield
    menuParticles: int
    fonts: UIFonts


@dataclass
class GameSettings:
    criticalWarningThreshold: int


@dataclass
class Settings:
    screen: ScreenSettings
    ship: ShipSettings
    resources: ResourceSettings
    scoring: ScoringSettings
    difficulty: DifficultySettings
    maze: MazeSettings
    enemies: EnemySettings
    replayEnemy: ReplayEnemySettings
    baby: BabySettings
    splitBoss: SplitBossSettings
    motherBoss: MotherBossSettings
    egg: EggSettings
    momentum: MomentumSettings
    projectile: ProjectileSettings
    visuals: VisualSettings
    colors: ColorsSettings
    exitPortal: ExitPortalSettings
    sound: SoundSettings
    controller: ControllerSettings
    powerups: PowerupSettings
    starAnimation: StarAnimationSettings
    ui: UISettings
    game: GameSettings


def _load_settings_json() -> dict:
    from utils.resource_path import resource_path
    path = Path(resource_path("config/settings.json"))
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_settings() -> Settings:
    raw = _load_settings_json()

    def _preset_map(presets: dict) -> Dict[str, MazeComplexityPreset]:
        return {
            key: MazeComplexityPreset(**value)
            for key, value in presets.items()
        }

    starfield = UIStarfield(**raw["ui"]["starfield"])
    animations = UIAnimations(**raw["ui"]["animations"])
    fonts = UIFonts(**raw["ui"]["fonts"])

    powerup_raw = raw["powerups"]
    powerup_settings = PowerupSettings(
        crystalSize=powerup_raw["crystalSize"],
        crystalSpawnChance=powerup_raw["crystalSpawnChance"],
        crystalRotationSpeed=powerup_raw["crystalRotationSpeed"],
        crystalGlowIntensity=powerup_raw["crystalGlowIntensity"],
        crystalColor=_as_color(tuple(powerup_raw["crystalColor"])),
        attractionRadius=powerup_raw["attractionRadius"],
        attractionSpeed=powerup_raw["attractionSpeed"],
        flashDurationFrames=powerup_raw["flashDurationFrames"],
        flashTintStrength=powerup_raw["flashTintStrength"],
        flashGlowMultiplier=powerup_raw["flashGlowMultiplier"],
        fireRateBaseCooldown=powerup_raw["fireRateBaseCooldown"],
        fireRateMultipliers=PowerupFireRateMultipliers(**powerup_raw["fireRateMultipliers"]),
        upgradedProjectile=PowerupUpgradedProjectile(
            spreadAngle=powerup_raw["upgradedProjectile"]["spreadAngle"],
            sizeMultiplier=powerup_raw["upgradedProjectile"]["sizeMultiplier"],
            speedMultiplier=powerup_raw["upgradedProjectile"]["speedMultiplier"],
            color=_as_color(tuple(powerup_raw["upgradedProjectile"]["color"])),
            glowColor=_as_color(tuple(powerup_raw["upgradedProjectile"]["glowColor"]))
        ),
        beyondLevel3=PowerupBeyondLevel3(**powerup_raw["beyondLevel3"])
        ,
        rotationSpeedMultiplier=powerup_raw["rotationSpeedMultiplier"]
    )

    colors_raw = raw["colors"]

    return Settings(
        screen=ScreenSettings(**raw["screen"]),
        ship=ShipSettings(**raw["ship"]),
        resources=ResourceSettings(**raw["resources"]),
        scoring=ScoringSettings(**raw["scoring"]),
        difficulty=DifficultySettings(**raw["difficulty"]),
        maze=MazeSettings(
            wallThickness=raw["maze"]["wallThickness"],
            cellSize=raw["maze"]["cellSize"],
            minPassageWidth=raw["maze"]["minPassageWidth"],
            wallHitPoints=raw["maze"]["wallHitPoints"],
            shipSpawnOffset=raw["maze"]["shipSpawnOffset"],
            complexityPresets=_preset_map(raw["maze"]["complexityPresets"])
        ),
        enemies=EnemySettings(**raw["enemies"]),
        replayEnemy=ReplayEnemySettings(
            windowSize=raw["replayEnemy"]["windowSize"],
            size=raw["replayEnemy"]["size"],
            color=_as_color(tuple(raw["replayEnemy"]["color"])),
            baseCount=raw["replayEnemy"]["baseCount"],
            scaleFactor=raw["replayEnemy"]["scaleFactor"]
        ),
        baby=BabySettings(**raw["baby"]),
        splitBoss=SplitBossSettings(**raw["splitBoss"]),
        motherBoss=MotherBossSettings(
            **{
                **raw["motherBoss"],
                "projectileGlowColor": _as_color(tuple(raw["motherBoss"]["projectileGlowColor"]))
            }
        ),
        egg=EggSettings(
            initialSize=raw["egg"]["initialSize"],
            maxSize=raw["egg"]["maxSize"],
            growthRateMin=raw["egg"]["growthRateMin"],
            growthRateMax=raw["egg"]["growthRateMax"],
            spawnOffsetRange=raw["egg"]["spawnOffsetRange"],
            baseCount=raw["egg"]["baseCount"],
            scaleFactor=raw["egg"]["scaleFactor"],
            color=_as_color(tuple(raw["egg"]["color"])),
            hitPoints=raw["egg"]["hitPoints"],
            babySpawnMin=raw["egg"]["babySpawnMin"],
            babySpawnMax=raw["egg"]["babySpawnMax"]
        ),
        momentum=MomentumSettings(**raw["momentum"]),
        projectile=ProjectileSettings(
            **{
                **raw["projectile"],
                "color": _as_color(tuple(raw["projectile"]["color"]))
            }
        ),
        visuals=VisualSettings(**raw["visuals"]),
        colors=ColorsSettings(
            background=_as_color(tuple(colors_raw["background"])),
            ship=_as_color(tuple(colors_raw["ship"])),
            walls=_as_color(tuple(colors_raw["walls"])),
            enemyStatic=_as_color(tuple(colors_raw["enemyStatic"])),
            enemyDynamic=_as_color(tuple(colors_raw["enemyDynamic"])),
            projectile=_as_color(tuple(colors_raw["projectile"])),
            exit=_as_color(tuple(colors_raw["exit"])),
            start=_as_color(tuple(colors_raw["start"])),
            text=_as_color(tuple(colors_raw["text"])),
            uiBackground=_as_color(tuple(colors_raw["uiBackground"])),
            shipNose=_as_color(tuple(colors_raw["shipNose"])),
            shipRear=_as_color(tuple(colors_raw["shipRear"])),
            shipDamagedNose=_as_color(tuple(colors_raw["shipDamagedNose"])),
            shipDamagedRear=_as_color(tuple(colors_raw["shipDamagedRear"]))
        ),
        exitPortal=ExitPortalSettings(**raw["exitPortal"]),
        sound=SoundSettings(**raw["sound"]),
        controller=ControllerSettings(**raw["controller"]),
        powerups=powerup_settings,
        starAnimation=StarAnimationSettings(**raw["starAnimation"]),
        ui=UISettings(
            splashDisplayDuration=raw["ui"]["splashDisplayDuration"],
            splashFadeInDuration=raw["ui"]["splashFadeInDuration"],
            splashFadeOutDuration=raw["ui"]["splashFadeOutDuration"],
            neonAsterStart=_as_color(tuple(raw["ui"]["neonAsterStart"])),
            neonAsterEnd=_as_color(tuple(raw["ui"]["neonAsterEnd"])),
            neonVoidStart=_as_color(tuple(raw["ui"]["neonVoidStart"])),
            neonVoidEnd=_as_color(tuple(raw["ui"]["neonVoidEnd"])),
            buttonAColor=_as_color(tuple(raw["ui"]["buttonAColor"])),
            buttonBColor=_as_color(tuple(raw["ui"]["buttonBColor"])),
            buttonGlowColor=_as_color(tuple(raw["ui"]["buttonGlowColor"])),
            animations=animations,
            starfield=starfield,
            menuParticles=raw["ui"]["menuParticles"],
            fonts=fonts
        ),
        game=GameSettings(**raw["game"])
    )


SETTINGS = load_settings()

STATES_DEFAULTS = {
    "splash": "splash",
    "menu": "menu",
    "profileSelection": "profile_selection",
    "playing": "playing",
    "levelComplete": "level_complete",
    "quitConfirm": "quit_confirm"
}

# Backwards-compatible constants
SCREEN_WIDTH = SETTINGS.screen.width
SCREEN_HEIGHT = SETTINGS.screen.height
FPS = SETTINGS.screen.fps
SCREEN_FULLSCREEN = SETTINGS.screen.fullscreen

SHIP_SIZE = SETTINGS.ship.size
SHIP_ROTATION_SPEED = SETTINGS.ship.rotationSpeed
SHIP_THRUST_FORCE = SETTINGS.ship.thrustForce
SHIP_FRICTION = SETTINGS.ship.friction
SHIP_MAX_SPEED = SETTINGS.ship.maxSpeed
COLLISION_RESTITUTION = SETTINGS.ship.collisionRestitution

INITIAL_FUEL = SETTINGS.resources.initialFuel
INITIAL_AMMO = SETTINGS.resources.initialAmmo
FUEL_CONSUMPTION_PER_THRUST = SETTINGS.resources.fuelPerThrust
AMMO_CONSUMPTION_PER_SHOT = SETTINGS.resources.ammoPerShot
SHIELD_FUEL_CONSUMPTION_PER_FRAME = SETTINGS.resources.shieldFuelPerFrame

MAX_LEVEL_SCORE = SETTINGS.scoring.maxLevelScore
TIME_PENALTY_RATE = SETTINGS.scoring.timePenaltyRate
COLLISION_PENALTY = SETTINGS.scoring.collisionPenalty
AMMO_PENALTY_RATE = SETTINGS.scoring.ammoPenaltyRate
FUEL_PENALTY_RATE = SETTINGS.scoring.fuelPenaltyRate
WALL_COLLISION_PENALTY = SETTINGS.scoring.wallCollisionPenalty
POWERUP_CRYSTAL_BONUS = SETTINGS.scoring.powerupCrystalBonus
ENEMY_BULLET_PENALTY = SETTINGS.scoring.enemyBulletPenalty

BASE_MAZE_SIZE = SETTINGS.difficulty.baseMazeSize
MAZE_SIZE_INCREMENT = SETTINGS.difficulty.mazeSizeIncrement
MAX_MAZE_SIZE = SETTINGS.difficulty.maxMazeSize
BASE_ENEMY_COUNT = SETTINGS.difficulty.baseEnemyCount
ENEMY_COUNT_INCREMENT = SETTINGS.difficulty.enemyCountIncrement
TUTORIAL_LEVELS = SETTINGS.difficulty.tutorialLevels

WALL_THICKNESS = SETTINGS.maze.wallThickness
CELL_SIZE = SETTINGS.maze.cellSize
MIN_PASSAGE_WIDTH = SETTINGS.maze.minPassageWidth
WALL_HIT_POINTS = SETTINGS.maze.wallHitPoints
SHIP_SPAWN_OFFSET = SETTINGS.maze.shipSpawnOffset

STATIC_ENEMY_SIZE = SETTINGS.enemies.staticSize
DYNAMIC_ENEMY_SIZE = SETTINGS.enemies.dynamicSize
ENEMY_PATROL_SPEED = SETTINGS.enemies.patrolSpeed
ENEMY_AGGRESSIVE_SPEED = SETTINGS.enemies.aggressiveSpeed
ENEMY_DAMAGE = SETTINGS.enemies.damage
ENEMY_STUCK_DETECTION_THRESHOLD = SETTINGS.enemies.stuckDetectionThreshold
ENEMY_SHIFT_ANGLE_MIN = SETTINGS.enemies.shiftAngleMin
ENEMY_SHIFT_ANGLE_MAX = SETTINGS.enemies.shiftAngleMax
ENEMY_SHIFT_DURATION_MIN = SETTINGS.enemies.shiftDurationMin
ENEMY_SHIFT_DURATION_MAX = SETTINGS.enemies.shiftDurationMax
ENEMY_FIRE_INTERVAL_MIN = SETTINGS.enemies.fireIntervalMin
ENEMY_FIRE_INTERVAL_MAX = SETTINGS.enemies.fireIntervalMax
ENEMY_FIRE_RANGE = SETTINGS.enemies.fireRange
REPLAY_ENEMY_FIRE_ANGLE_TOLERANCE = SETTINGS.enemies.replayFireAngleTolerance

REPLAY_ENEMY_WINDOW_SIZE = SETTINGS.replayEnemy.windowSize
REPLAY_ENEMY_SIZE = SETTINGS.replayEnemy.size
REPLAY_ENEMY_COLOR = SETTINGS.replayEnemy.color
REPLAY_ENEMY_BASE_COUNT = SETTINGS.replayEnemy.baseCount
REPLAY_ENEMY_SCALE_FACTOR = SETTINGS.replayEnemy.scaleFactor

BABY_SIZE = SETTINGS.baby.size
BABY_SPEED_MULTIPLIER = SETTINGS.baby.speedMultiplier

SPLIT_BOSS_SIZE_MULTIPLIER = SETTINGS.splitBoss.sizeMultiplier
SPLIT_BOSS_HIT_POINTS = SETTINGS.splitBoss.hitPoints
SPLIT_BOSS_SPAWN_OFFSET_RANGE = SETTINGS.splitBoss.spawnOffsetRange
SPLIT_BOSS_SPLIT_VELOCITY_MAGNITUDE = SETTINGS.splitBoss.splitVelocityMagnitude
SPLIT_BOSS_BASE_COUNT = SETTINGS.splitBoss.baseCount
SPLIT_BOSS_SCALE_FACTOR = SETTINGS.splitBoss.scaleFactor
SPLIT_BOSS_CHILD_COUNT = SETTINGS.splitBoss.childrenCount

MOTHER_BOSS_SIZE_MULTIPLIER = SETTINGS.motherBoss.sizeMultiplier
MOTHER_BOSS_HIT_POINTS = SETTINGS.motherBoss.hitPoints
MOTHER_BOSS_EGG_LAY_INTERVAL = SETTINGS.motherBoss.eggLayInterval
MOTHER_BOSS_BASE_COUNT = SETTINGS.motherBoss.baseCount
MOTHER_BOSS_SCALE_FACTOR = SETTINGS.motherBoss.scaleFactor

MOTHER_BOSS_LINE_GLOW_INTENSITY_MAX = SETTINGS.motherBoss.lineGlowIntensityMax
MOTHER_BOSS_BLINK_FREQUENCY_MULTIPLIER_MAX = SETTINGS.motherBoss.blinkFrequencyMultiplierMax
MOTHER_BOSS_BLINK_DURATION_MULTIPLIER_MAX = SETTINGS.motherBoss.blinkDurationMultiplierMax

MOTHER_BOSS_PROJECTILE_SPEED_MULTIPLIER = SETTINGS.motherBoss.projectileSpeedMultiplier
MOTHER_BOSS_PROJECTILE_IMPACT_MULTIPLIER = SETTINGS.motherBoss.projectileImpactMultiplier
MOTHER_BOSS_PROJECTILE_GLOW_COLOR = SETTINGS.motherBoss.projectileGlowColor
MOTHER_BOSS_PROJECTILE_GLOW_RADIUS_MULTIPLIER = SETTINGS.motherBoss.projectileGlowRadiusMultiplier
MOTHER_BOSS_PROJECTILE_GLOW_INTENSITY = SETTINGS.motherBoss.projectileGlowIntensity

EGG_INITIAL_SIZE = SETTINGS.egg.initialSize
EGG_MAX_SIZE = SETTINGS.egg.maxSize
EGG_GROWTH_RATE_MIN = SETTINGS.egg.growthRateMin
EGG_GROWTH_RATE_MAX = SETTINGS.egg.growthRateMax
EGG_SPAWN_OFFSET_RANGE = SETTINGS.egg.spawnOffsetRange
EGG_BASE_COUNT = SETTINGS.egg.baseCount
EGG_SCALE_FACTOR = SETTINGS.egg.scaleFactor
COLOR_EGG = SETTINGS.egg.color
EGG_HIT_POINTS = SETTINGS.egg.hitPoints
EGG_BABY_SPAWN_MIN = SETTINGS.egg.babySpawnMin
EGG_BABY_SPAWN_MAX = SETTINGS.egg.babySpawnMax

STATIC_ENEMY_HIT_POINTS = SETTINGS.momentum.staticEnemyHitPoints
MOMENTUM_TRANSFER_FACTOR = SETTINGS.momentum.transferFactor
FRICTION_COEFFICIENT = SETTINGS.momentum.frictionCoefficient
MIN_VELOCITY_THRESHOLD = SETTINGS.momentum.minVelocityThreshold

PROJECTILE_SPEED = SETTINGS.projectile.speed
PROJECTILE_SIZE = SETTINGS.projectile.size
PROJECTILE_LIFETIME = SETTINGS.projectile.lifetime
COLOR_ENEMY_PROJECTILE = SETTINGS.projectile.color
PROJECTILE_IMPACT_FORCE = SETTINGS.projectile.impactForce

SHIP_GLOW_INTENSITY = SETTINGS.visuals.shipGlowIntensity
SHIP_GLOW_RADIUS_MULTIPLIER = SETTINGS.visuals.shipGlowRadiusMultiplier
ENEMY_PULSE_SPEED = SETTINGS.visuals.enemyPulseSpeed
ENEMY_PULSE_AMPLITUDE = SETTINGS.visuals.enemyPulseAmplitude
THRUST_PLUME_LENGTH = SETTINGS.visuals.thrustPlumeLength
THRUST_PLUME_PARTICLES = SETTINGS.visuals.thrustPlumeParticles

COLOR_BACKGROUND = SETTINGS.colors.background
COLOR_SHIP = SETTINGS.colors.ship
COLOR_WALLS = SETTINGS.colors.walls
COLOR_ENEMY_STATIC = SETTINGS.colors.enemyStatic
COLOR_ENEMY_DYNAMIC = SETTINGS.colors.enemyDynamic
COLOR_PROJECTILE = SETTINGS.colors.projectile
COLOR_EXIT = SETTINGS.colors.exit
COLOR_START = SETTINGS.colors.start
COLOR_TEXT = SETTINGS.colors.text
COLOR_UI_BG = SETTINGS.colors.uiBackground
COLOR_SHIP_NOSE = SETTINGS.colors.shipNose
COLOR_SHIP_REAR = SETTINGS.colors.shipRear
COLOR_SHIP_DAMAGED_NOSE = SETTINGS.colors.shipDamagedNose
COLOR_SHIP_DAMAGED_REAR = SETTINGS.colors.shipDamagedRear

EXIT_PORTAL_ATTRACTION_RADIUS = SETTINGS.exitPortal.attractionRadius
EXIT_PORTAL_ATTRACTION_FORCE_MULTIPLIER = SETTINGS.exitPortal.attractionForceMultiplier
EXIT_PORTAL_GLOW_MULTIPLIER = SETTINGS.exitPortal.glowMultiplier
EXIT_PORTAL_GLOW_LAYER_OFFSET = SETTINGS.exitPortal.glowLayerOffset

SOUND_ENABLED = SETTINGS.sound.enabled
SOUND_SAMPLE_RATE = SETTINGS.sound.sampleRate
THRUSTER_SOUND_VOLUME = SETTINGS.sound.thrusterVolume
SHOOT_SOUND_VOLUME = SETTINGS.sound.shootVolume
ENEMY_DESTROY_SOUND_VOLUME = SETTINGS.sound.enemyDestroyVolume
EXIT_WARBLE_SOUND_VOLUME = SETTINGS.sound.exitWarbleVolume
POWERUP_ACTIVATION_SOUND_VOLUME = SETTINGS.sound.powerupActivationVolume
THRUSTER_NOISE_DURATION = SETTINGS.sound.thrusterNoiseDuration
SHOOT_BLIP_FREQUENCY = SETTINGS.sound.shootBlipFrequency
SHOOT_BLIP_DURATION = SETTINGS.sound.shootBlipDuration
BAD_HIT_SOUND_VOLUME = SETTINGS.sound.hitSoundVolume

CONTROLLER_DEADZONE = SETTINGS.controller.deadzone
CONTROLLER_TRIGGER_THRESHOLD = SETTINGS.controller.triggerThreshold

POWERUP_CRYSTAL_SIZE = SETTINGS.powerups.crystalSize
POWERUP_CRYSTAL_SPAWN_CHANCE = SETTINGS.powerups.crystalSpawnChance
POWERUP_CRYSTAL_ROTATION_SPEED = SETTINGS.powerups.crystalRotationSpeed
POWERUP_CRYSTAL_GLOW_INTENSITY = SETTINGS.powerups.crystalGlowIntensity
COLOR_POWERUP_CRYSTAL = SETTINGS.powerups.crystalColor
POWERUP_CRYSTAL_ATTRACTION_RADIUS = SETTINGS.powerups.attractionRadius
POWERUP_CRYSTAL_ATTRACTION_SPEED = SETTINGS.powerups.attractionSpeed
POWERUP_FLASH_DURATION_FRAMES = SETTINGS.powerups.flashDurationFrames
POWERUP_FLASH_TINT_STRENGTH = SETTINGS.powerups.flashTintStrength
POWERUP_FLASH_GLOW_MULTIPLIER = SETTINGS.powerups.flashGlowMultiplier

POWERUP_LEVEL_1_FIRE_RATE_MULTIPLIER = SETTINGS.powerups.fireRateMultipliers.level1
POWERUP_LEVEL_2_FIRE_RATE_MULTIPLIER = SETTINGS.powerups.fireRateMultipliers.level2
POWERUP_LEVEL_3_FIRE_RATE_MULTIPLIER = SETTINGS.powerups.fireRateMultipliers.level3
UPGRADED_PROJECTILE_SPREAD_ANGLE = SETTINGS.powerups.upgradedProjectile.spreadAngle
UPGRADED_PROJECTILE_SIZE_MULTIPLIER = SETTINGS.powerups.upgradedProjectile.sizeMultiplier
UPGRADED_PROJECTILE_SPEED_MULTIPLIER = SETTINGS.powerups.upgradedProjectile.speedMultiplier
COLOR_UPGRADED_PROJECTILE = SETTINGS.powerups.upgradedProjectile.color
COLOR_UPGRADED_SHIP_GLOW = SETTINGS.powerups.upgradedProjectile.glowColor

POWERUP_BEYOND_LEVEL_3_SIZE_INCREMENT = SETTINGS.powerups.beyondLevel3.sizeIncrement
POWERUP_BEYOND_LEVEL_3_SPEED_INCREMENT = SETTINGS.powerups.beyondLevel3.speedIncrement
POWERUP_BEYOND_LEVEL_3_GLOW_INTENSITY_INCREMENT = SETTINGS.powerups.beyondLevel3.glowIntensityIncrement
POWERUP_BEYOND_LEVEL_3_HUE_ROTATION = SETTINGS.powerups.beyondLevel3.hueRotation
POWERUP_ROTATION_SPEED_MULTIPLIER = SETTINGS.powerups.rotationSpeedMultiplier

STAR_APPEAR_DURATION = SETTINGS.starAnimation.appearDuration
STAR_TWINKLE_SPEED = SETTINGS.starAnimation.twinkleSpeed
STAR_TWINKLE_INTENSITY = SETTINGS.starAnimation.twinkleIntensity
STAR_TINKLE_BASE_PITCH = SETTINGS.starAnimation.tinkleBasePitch
STAR_TINKLE_PITCH_INCREMENT = SETTINGS.starAnimation.tinklePitchIncrement
LEVEL_COMPLETE_STAR_SIZE = SETTINGS.starAnimation.levelCompleteStarSize

STATE_SPLASH = STATES_DEFAULTS["splash"]
STATE_MENU = STATES_DEFAULTS["menu"]
STATE_PROFILE_SELECTION = STATES_DEFAULTS["profileSelection"]
STATE_PLAYING = STATES_DEFAULTS["playing"]
STATE_LEVEL_COMPLETE = STATES_DEFAULTS["levelComplete"]
STATE_QUIT_CONFIRM = STATES_DEFAULTS["quitConfirm"]

SPLASH_DISPLAY_DURATION = SETTINGS.ui.splashDisplayDuration
SPLASH_FADE_IN_DURATION = SETTINGS.ui.splashFadeInDuration
SPLASH_FADE_OUT_DURATION = SETTINGS.ui.splashFadeOutDuration

COLOR_NEON_ASTER_START = SETTINGS.ui.neonAsterStart
COLOR_NEON_ASTER_END = SETTINGS.ui.neonAsterEnd
COLOR_NEON_VOID_START = SETTINGS.ui.neonVoidStart
COLOR_NEON_VOID_END = SETTINGS.ui.neonVoidEnd
COLOR_BUTTON_A = SETTINGS.ui.buttonAColor
COLOR_BUTTON_B = SETTINGS.ui.buttonBColor
COLOR_BUTTON_GLOW = SETTINGS.ui.buttonGlowColor

NEON_GLOW_INTENSITY = SETTINGS.ui.animations.neonGlowIntensity
NEON_GLOW_PULSE_SPEED = SETTINGS.ui.animations.neonGlowPulseSpeed
BUTTON_GLOW_INTENSITY = SETTINGS.ui.animations.buttonGlowIntensity
BUTTON_GLOW_PULSE_SPEED = SETTINGS.ui.animations.buttonGlowPulseSpeed
STARFIELD_STAR_COUNT = SETTINGS.ui.starfield.starCount
STARFIELD_TWINKLE_SPEED = SETTINGS.ui.starfield.twinkleSpeed
MENU_PARTICLE_COUNT = SETTINGS.ui.menuParticles

FONT_SIZE_TITLE = SETTINGS.ui.fonts.title
FONT_SIZE_SUBTITLE = SETTINGS.ui.fonts.subtitle
FONT_SIZE_BUTTON = SETTINGS.ui.fonts.button
FONT_SIZE_HINT = SETTINGS.ui.fonts.hint