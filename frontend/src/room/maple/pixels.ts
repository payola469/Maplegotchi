// Maple's pixel art as text grids: one character per pixel, "." is transparent.
// Every other character is a key in MAPLE_PALETTE. Parts are composed into
// whole frames by sprites.ts; nothing here knows about Pixi.
//
// Character: a chibi with short layered black hair, dark brown eyes behind black
// glasses, orange headphones and a dark green hoodie (navy trousers, brown shoes).
// All art is original.

export type Grid = readonly string[];

export const MAPLE_PALETTE: Readonly<Record<string, number>> = {
  K: 0x2a1d17, // outline
  H: 0x1d1a22, // hair
  h: 0x3b3646, // hair highlight
  S: 0xf2c9a0, // skin
  s: 0xd9a77e, // skin shade (eyelids)
  O: 0xd9773a, // headphones
  o: 0xa9542a, // headphones shade
  G: 0x2f5d46, // hoodie
  g: 0x24493a, // hoodie shade
  L: 0x3f7a5a, // hoodie highlight
  C: 0xf6ebd6, // drawstrings
  P: 0x26345a, // trousers
  p: 0x1a2440, // trousers shade
  B: 0x5e3a21, // shoes
  E: 0x5c3317, // eyes (dark brown, warm enough to read behind black frames)
  W: 0xffffff, // glint
  R: 0xf08a7a, // blush
  M: 0x7a3a2a, // mouth
  F: 0x15121a, // glasses frame
  N: 0x2c3e66, // book cover
  Y: 0xd9a441, // book spine / pencil / sparkle
  Z: 0x5b6fa6, // sleepy "z" and sleepy text
  r: 0xd9481f, // heart
};

// ---- Head (24 x 14). The face area is 12 x 6 at (6, 8). ----------------------

export const HEAD: Grid = [
  "........KKKKKKKK........",
  "......KKOOOOOOOOKK......",
  ".....KOHHHHHHHHHHOK.....",
  "....KOHHhHHHHHHhHHOK....",
  "...KOOHhHHHHHHHHhHOOK...",
  "...KOHHhHHHHHHHHhHHOK...",
  "...KOHHSHHHSSHHHSHHOK...",
  "..KOOHSSSSSSSSSSSSHOOK..",
  "..KOoHSSSSSSSSSSSSHoOK..",
  "..KOoHSSSSSSSSSSSSHoOK..",
  "..KOOHSSSSSSSSSSSSHOOK..",
  "...KKHSSSSSSSSSSSSHKK...",
  "....KSSSSSSSSSSSSSSK....",
  ".....KKSSSSSSSSSSKK.....",
];

/** Face overlays (12 x 6): glasses, eyes, mouth. One per expression, plus "asleep" for the sleep pose. */
export const FACES = {
  calm: [
    ".FFFF..FFFF.",
    "F.WE.FF.WE.F",
    "F.EE.FF.EE.F",
    ".FFFF..FFFF.",
    "....M..M....",
    ".....MM.....",
  ],
  happy: [
    ".FFFF..FFFF.",
    "F.EE.FF.EE.F",
    "FE..EFFE..EF",
    ".FFFF..FFFF.",
    "R...MMMM...R",
    ".....MM.....",
  ],
  curious: [
    ".FFFF..FFFF.",
    "FWEE.FFWEE.F",
    "FEEE.FFEEE.F",
    ".FFFF..FFFF.",
    ".....MM.....",
    ".....MM.....",
  ],
  sleepy: [
    ".FFFF..FFFF.",
    "FssssFFssssF",
    "F.EE.FF.EE.F",
    ".FFFF..FFFF.",
    "............",
    ".....M......",
  ],
  focused: [
    ".FFFF..FFFF.",
    "F.EEWFF.EEWF",
    "F.EE.FF.EE.F",
    ".FFFF..FFFF.",
    "............",
    "....MMMM....",
  ],
  asleep: [
    ".FFFF..FFFF.",
    "F....FF....F",
    "F.EEEFFEEE.F",
    ".FFFF..FFFF.",
    "............",
    ".....MM.....",
  ],
} as const satisfies Record<string, Grid>;

// ---- Body parts (24 wide) -------------------------------------------------------

/** Hood, neck and shoulders (4 rows); shared by every upright pose. */
export const TORSO_TOP: Grid = [
  "......KGGSSSSSSGGK......",
  ".....KGLGGGGGGGGLGK.....",
  "....KGGLGCGGGGCGLGGK....",
  "...KGGGLGCGGGGCGLGGGK...",
];

/** Standing: arms down, pocket, hem, top of the trousers (6 rows). */
export const TORSO_STAND: Grid = [
  "...KGgGLGGGGGGGGLGgGK...",
  "...KGgGGGGGGGGGGGGgGK...",
  "...KSgGGGggggggGGGgSK...",
  "...KSKGGGGGGGGGGGGKSK...",
  "....KKggggggggggggKK....",
  ".....KPPPPPPPPPPPPK.....",
];

export const LEGS_STAND: Grid = [
  ".....KPPPPPpKpPPPPK.....",
  ".....KPPPPK..KPPPPK.....",
  "....KBBBBBK..KBBBBBK....",
  "....KKKKKKK..KKKKKKK....",
];

/** Walking: the left foot lifted (A) or the right foot lifted (B). */
export const LEGS_WALK_A: Grid = [
  ".....KPPPPPpKpPPPPK.....",
  ".....KBBBBK..KPPPPK.....",
  ".....KKKKKK..KBBBBBK....",
  ".............KKKKKKK....",
];

export const LEGS_WALK_B: Grid = [
  ".....KPPPPPpKpPPPPK.....",
  ".....KPPPPK..KBBBBK.....",
  "....KBBBBBK..KKKKKK.....",
  "....KKKKKKK.............",
];

/** Arms for seated and floor poses (2 rows each). */
export const ARMS_WRITE: Grid = [
  "...KGgGGGGGGGGGGgSSYK...",
  "...KSgGGGggggGGGGgSSK...",
];

export const ARMS_TYPE: Grid = [
  "...KGgGGGGGGGGGGGGgGK...",
  "...KGgGSSGGGGGGSSGgGK...",
];

export const ARMS_HOLD: Grid = [
  "...KGgGGGGGGGGGGGGgGK...",
  "...KGgSGGGGGGGGGGSgGK...",
];

export const ARMS_MUG: Grid = [
  "...KGgGGGGGGGGGGGGgGK...",
  "...KGgGGSOOOOSGGGGgGK...",
];

/** Sitting on a chair: hem, thighs, lower legs, shoes (5 rows). */
export const SEAT_LEGS: Grid = [
  "....KKggggggggggggKK....",
  "....KPPPPPPPPPPPPPPK....",
  ".....KPPPPK..KPPPPK.....",
  "....KBBBBBK..KBBBBBK....",
  "....KKKKKKK..KKKKKKK....",
];

/** Sitting cross-legged on the floor: hem and folded legs (4 rows). */
export const FLOOR_LEGS: Grid = [
  "....KKggggggggggggKK....",
  "..KPPPPPPPPPPPPPPPPPPK..",
  ".KBBPPPPPPPPPPPPPPPPBBK.",
  ".KKKKKKKKKKKKKKKKKKKKKK.",
];

/**
 * Sleeping: the quilt pulled up to the shoulder, body mound to the right of the
 * head (22 x 8). The sleep frame puts the head on the pillow and this beside it.
 */
export const QUILT: Grid = [
  "......KKKKKKKK........",
  "....KKGGLGGGLGKK......",
  "KKKKGGGGGGLGGGGGKKK...",
  "KCCCGGLGGGGGGGLGGGGK..",
  "KCCCGGGGGLGGGGGGGLGGK.",
  "KCCCGGLGGGGGGLGGGGGGGK",
  "KggggggggggggggggggggK",
  "KKKKKKKKKKKKKKKKKKKKKK",
];

/** Open book held up in front, pages towards the viewer (12 x 5). */
export const BOOK: Grid = [
  ".KKKK..KKKK.",
  "KCCCCKKCCCCK",
  "KCKKCKKCKKCK",
  "KCCCCKKCCCCK",
  ".NNNNYYNNNN.",
];

// ---- Bubble and sleep glyphs ------------------------------------------------------

export const GLYPH_HI: Grid = [
  "K.K.K.K",
  "K.K...K",
  "KKK.K.K",
  "K.K.K..",
  "K.K.K.K",
];

export const GLYPH_SLEEPY_HI: Grid = [
  "......Z...Z",
  "......Z....",
  "......ZZZ.Z",
  "......Z.Z.Z",
  "Z.Z.Z.Z.Z.Z",
];

export const GLYPH_HEART: Grid = [
  ".rr.rr.",
  "rWrrrrr",
  "rrrrrrr",
  ".rrrrr.",
  "..rrr..",
  "...r...",
];

export const GLYPH_SPARKLE: Grid = [
  "..Y..",
  "..Y..",
  "YYWYY",
  "..Y..",
  "..Y..",
];

export const GLYPH_Z: Grid = [
  "ZZZZ",
  "..Z.",
  ".Z..",
  "ZZZZ",
];
