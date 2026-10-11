from pydantic import BaseModel, ConfigDict

MULT = 6364136223846793005
MASK64 = (1 << 64) - 1
MASK32 = 0xFFFFFFFF
INITSEQ = 54


class RngState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algo: str = "pcg32"
    seed: int
    state: int
    inc: int
    draws: int = 0


class Rng:
    def __init__(self, seed: int):
        inc = ((INITSEQ << 1) | 1) & MASK64
        state = (0 * MULT + inc) & MASK64
        state = (state + seed) & MASK64
        state = (state * MULT + inc) & MASK64
        self._seed = seed
        self._state = state
        self._inc = inc
        self._draws = 0

    @classmethod
    def from_state(cls, state: RngState) -> "Rng":
        if state.algo != "pcg32":
            raise ValueError(f"неизвестный алгоритм ГСЧ: {state.algo!r}")
        rng = cls(state.seed)
        rng._state = state.state
        rng._inc = state.inc
        rng._draws = state.draws
        return rng

    @property
    def state(self) -> RngState:
        return RngState(
            algo="pcg32",
            seed=self._seed,
            state=self._state,
            inc=self._inc,
            draws=self._draws,
        )

    @property
    def draws(self) -> int:
        return self._draws

    def next_u32(self) -> int:
        old = self._state
        self._state = (old * MULT + self._inc) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & MASK32
        rot = old >> 59
        self._draws += 1
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & MASK32

    def randbelow(self, n: int) -> int:
        if n < 1:
            raise ValueError("n должно быть >= 1")
        if n > 2**32:
            raise ValueError("n должно быть <= 2**32")
        # отбрасываем значения из неполного хвоста, чтобы не было смещения
        threshold = (1 << 32) % n
        while True:
            value = self.next_u32()
            if value >= threshold:
                return value % n

    def randint(self, a: int, b: int) -> int:
        return a + self.randbelow(b - a + 1)

    def d(self, sides: int) -> int:
        return self.randint(1, sides)
