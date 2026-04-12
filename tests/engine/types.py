"""
RED4 Engine Simulation -- Primitive Types
=========================================

Mirrors the value types defined in:
  scripts/Base/Imports/FixedPoint.reds
  scripts/Base/Addons/WorldPosition.reds
  scripts/Base/Addons/WorldTransform.reds
  scripts/Utils/Vector2.reds, Vector3.reds

These are pure data objects with no system dependencies.
"""

import math
import enum


# ── FixedPoint (scripts/Base/Imports/FixedPoint.reds) ──────────────

class FixedPoint:
    """16.16 fixed-point number used by WorldPosition."""

    __slots__ = ('Bits',)

    def __init__(self, bits=0):
        self.Bits = bits

    @staticmethod
    def from_float(f):
        return FixedPoint(bits=int(f * 65536))

    def to_float(self):
        return self.Bits / 65536.0

    def __repr__(self):
        return f"FP({self.to_float():.4f})"


# ── CName ──────────────────────────────────────────────────────────

class CName:
    """Engine interned name.  Redscript: n"SomeName" """

    __slots__ = ('_value',)

    def __init__(self, value=""):
        self._value = value

    def __eq__(self, other):
        if isinstance(other, CName):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return NotImplemented

    def __hash__(self):
        return hash(self._value)

    def __str__(self):
        return self._value

    def __repr__(self):
        return f'n"{self._value}"'


# ── EntityID (scripts/Entity/EntityID.reds) ────────────────────────

_next_entity_id = 1000


class EntityID:
    """Unique entity identifier.  Wraps an integer hash."""

    __slots__ = ('_hash',)

    def __init__(self, hash_val=0):
        self._hash = hash_val

    @staticmethod
    def next_id():
        global _next_entity_id
        _next_entity_id += 1
        return EntityID(_next_entity_id)

    @staticmethod
    def reset_counter():
        global _next_entity_id
        _next_entity_id = 1000

    @staticmethod
    def FromHash(h):
        return EntityID(h)

    @staticmethod
    def ToHash(eid):
        return eid._hash

    def IsDefined(self):
        return self._hash != 0

    def __eq__(self, other):
        if isinstance(other, EntityID):
            return self._hash == other._hash
        return NotImplemented

    def __hash__(self):
        return hash(self._hash)

    def __repr__(self):
        return f"EID({self._hash})"


# ── Input Enums ────────────────────────────────────────────────────

class EInputKey(enum.Enum):
    IK_None = 0
    IK_F1 = 1; IK_F2 = 2; IK_F3 = 3; IK_F4 = 4
    IK_F5 = 5; IK_F6 = 6; IK_F7 = 7; IK_F8 = 8
    IK_F9 = 9; IK_F10 = 10; IK_F11 = 11; IK_F12 = 12
    IK_Numpad0 = 20; IK_Numpad1 = 21; IK_Numpad2 = 22
    IK_Numpad3 = 23; IK_Numpad4 = 24; IK_Numpad5 = 25


class EInputAction(enum.Enum):
    IACT_None = 0
    IACT_Press = 1
    IACT_Release = 2
    IACT_Hold = 3


# ── Vectors ────────────────────────────────────────────────────────

class Vector4:
    """4-component vector.  W = 0 for positions/directions."""

    __slots__ = ('X', 'Y', 'Z', 'W')

    def __init__(self, X=0.0, Y=0.0, Z=0.0, W=0.0):
        self.X = float(X)
        self.Y = float(Y)
        self.Z = float(Z)
        self.W = float(W)

    def distance_to(self, other):
        dx = self.X - other.X
        dy = self.Y - other.Y
        dz = self.Z - other.Z
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def __repr__(self):
        return f"V4({self.X:.2f}, {self.Y:.2f}, {self.Z:.2f})"


class Vector3:
    __slots__ = ('X', 'Y', 'Z')

    def __init__(self, X=0.0, Y=0.0, Z=0.0):
        self.X = float(X)
        self.Y = float(Y)
        self.Z = float(Z)

    def __repr__(self):
        return f"V3({self.X:.2f}, {self.Y:.2f}, {self.Z:.2f})"


# ── Quaternion ─────────────────────────────────────────────────────

class Quaternion:
    """Rotation quaternion.

    WARNING: Default (0,0,0,0) is DEGENERATE -- NOT identity.
    Use Quaternion.identity() for (0,0,0,1).
    """

    __slots__ = ('i', 'j', 'k', 'r')

    def __init__(self, i=0.0, j=0.0, k=0.0, r=0.0):
        self.i = float(i)
        self.j = float(j)
        self.k = float(k)
        self.r = float(r)

    @staticmethod
    def identity():
        return Quaternion(0, 0, 0, 1)

    @staticmethod
    def from_yaw(degrees):
        """Create from yaw (heading) rotation around Z axis."""
        rad = math.radians(degrees) / 2
        return Quaternion(i=0, j=0, k=math.sin(rad), r=math.cos(rad))

    def is_identity(self):
        return (abs(self.i) < 1e-6 and abs(self.j) < 1e-6
                and abs(self.k) < 1e-6 and abs(self.r - 1.0) < 1e-6)

    def is_zero(self):
        return (abs(self.i) < 1e-6 and abs(self.j) < 1e-6
                and abs(self.k) < 1e-6 and abs(self.r) < 1e-6)

    def is_valid(self):
        length = math.sqrt(self.i**2 + self.j**2 + self.k**2 + self.r**2)
        return abs(length - 1.0) < 0.01

    def copy(self):
        return Quaternion(self.i, self.j, self.k, self.r)

    def __repr__(self):
        return f"Q({self.i:.3f}, {self.j:.3f}, {self.k:.3f}, {self.r:.3f})"


# ── WorldPosition / WorldTransform ────────────────────────────────

class WorldPosition:
    """scripts/Base/Addons/WorldPosition.reds -- FixedPoint x, y, z."""

    __slots__ = ('x', 'y', 'z')

    def __init__(self):
        self.x = FixedPoint()
        self.y = FixedPoint()
        self.z = FixedPoint()


class WorldTransform:
    """scripts/Base/Addons/WorldTransform.reds

    Position: WorldPosition
    Orientation: Quaternion  (default is ZERO, not identity!)
    """

    __slots__ = ('Position', 'Orientation')

    def __init__(self):
        self.Position = WorldPosition()
        self.Orientation = Quaternion()  # (0,0,0,0) -- degenerate!


# ── DelayID ────────────────────────────────────────────────────────

class DelayID:
    __slots__ = ('_id',)

    def __init__(self, id_val=0):
        self._id = id_val

    def __repr__(self):
        return f"DelayID({self._id})"
