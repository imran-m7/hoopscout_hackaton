import type { AgeGroup, Gender, Hand, PlayerSummary, Position, SkillScores } from "@/lib/types";
import { rankGroupLabel } from "@/lib/format";
import { DEFAULT_WEIGHTS, SKILLS, rankPlayers, weightedAverage } from "@/lib/scoring";

// Sample data — realistic but invented players for demo mode.
type Spec = [
  id: string,
  name: string,
  gender: Gender,
  group: AgeGroup,
  quarter: 1 | 2 | 3 | 4,
  heightDiff: number,
  position: Position,
  hand: Hand,
  years: number,
  club: string,
  town: string,
  avgSkill: number,
  fairAdj: number,
  isReal: boolean,
  provisional: string | null,
];

const WISLA = "Wisła Kraków Juniors";
const MKS = "MKS Tarnów";
const BOCH = "KS Bochnia";
const SOKOL = "Sokół Nowy Sącz";

const SPECS: Spec[] = [
  // Boys U14 (9)
  ["p01", "Luka Petrović", "boy", "U14", 4, -8, "guard", "left", 2, BOCH, "Bochnia", 61, 16, true, null],
  ["p02", "Marko Nowak", "boy", "U14", 1, 11, "center", "right", 6, WISLA, "Kraków", 74, -4, true, null],
  ["p03", "Jakub Wójcik", "boy", "U14", 1, 7, "forward", "right", 5, WISLA, "Kraków", 72, -3, false, null],
  ["p04", "Filip Kowalski", "boy", "U14", 2, 5, "forward", "right", 5, MKS, "Tarnów", 70, -2, false, null],
  ["p05", "Antoni Zieliński", "boy", "U14", 2, 3, "guard", "right", 4, SOKOL, "Nowy Sącz", 69, -1, false, null],
  ["p06", "Szymon Lewandowski", "boy", "U14", 2, 1, "forward", "left", 4, MKS, "Tarnów", 67, 0, false, null],
  ["p07", "Igor Kamiński", "boy", "U14", 3, 0, "guard", "right", 3, WISLA, "Kraków", 66, 1, false, null],
  ["p08", "Oskar Dąbrowski", "boy", "U14", 3, -2, "center", "right", 3, BOCH, "Bochnia", 64, 2, false, null],
  ["p09", "Emil Mazur", "boy", "U14", 4, -6, "guard", "right", 1, SOKOL, "Nowy Sącz", 60, 14, false, null],
  // Girls U14 (6)
  ["p10", "Zofia Krawczyk", "girl", "U14", 1, 9, "center", "right", 6, WISLA, "Kraków", 73, -3, false, null],
  ["p11", "Maja Piotrowska", "girl", "U14", 1, 6, "forward", "right", 5, MKS, "Tarnów", 71, -2, false, null],
  ["p12", "Hanna Grabowska", "girl", "U14", 2, 3, "guard", "right", 4, SOKOL, "Nowy Sącz", 69, -1, false, null],
  ["p13", "Lena Pawlak", "girl", "U14", 2, 1, "forward", "left", 4, WISLA, "Kraków", 67, 0, false, null],
  ["p14", "Julia Michalska", "girl", "U14", 3, -1, "guard", "right", 3, BOCH, "Bochnia", 65, 1, false, null],
  ["p15", "Ana Jovanović", "girl", "U14", 4, -7, "guard", "right", 2, MKS, "Tarnów", 62, 13, true, null],
  // Boys U12 (3)
  ["p16", "Nikola Babić", "boy", "U12", 1, 6, "forward", "right", 4, WISLA, "Kraków", 66, -2, false, null],
  ["p17", "Adam Król", "boy", "U12", 3, -2, "guard", "left", 2, BOCH, "Bochnia", 63, 1, false, null],
  ["p18", "Tymon Wieczorek", "boy", "U12", 4, -4, "guard", "right", 1, SOKOL, "Nowy Sącz", 60, 3, true, "only 4 shots, need 6"],
  // Girls U12 (2)
  ["p19", "Pola Jabłońska", "girl", "U12", 2, 2, "forward", "right", 3, MKS, "Tarnów", 64, -1, false, null],
  ["p20", "Mila Adamczyk", "girl", "U12", 4, -3, "guard", "right", 2, WISLA, "Kraków", 61, 2, false, null],
  // Boys U16 (2)
  ["p21", "Stefan Marković", "boy", "U16", 1, 9, "center", "right", 7, WISLA, "Kraków", 76, -3, false, null],
  ["p22", "Kacper Sikora", "boy", "U16", 3, -3, "guard", "right", 3, MKS, "Tarnów", 71, 2, false, null],
  // Girls U16 (2)
  ["p23", "Wiktoria Baran", "girl", "U16", 2, 4, "forward", "right", 6, SOKOL, "Nowy Sącz", 70, -1, false, null],
  ["p24", "Iva Kovačević", "girl", "U16", 4, -2, "guard", "left", 2, BOCH, "Bochnia", 65, 0, false, "dribbling video too short (12 s, need 20 s)"],
];

const OFFSETS = [6, -2, 3, -7, 1, -1];
const GROUP_BASE_MONTHS: Record<AgeGroup, number> = { U10: 108, U12: 132, U14: 156, U16: 180, U18: 204 };
const HEIGHT_AVG: Record<string, number> = { "boy-U12": 146, "girl-U12": 147, "boy-U14": 160, "girl-U14": 158, "boy-U16": 172, "girl-U16": 162 };
const AGE_ADJ: Record<1 | 2 | 3 | 4, number> = { 1: -2, 2: -1, 3: 1, 4: 3 };

export function experienceBonus(years: number): number {
  return years <= 2 ? 2 : years <= 4 ? 1 : 0;
}

function round1(n: number) {
  return Math.round(n * 10) / 10;
}

export function buildMockPlayers(): PlayerSummary[] {
  const players = SPECS.map((s, i): PlayerSummary => {
    const [id, name, gender, group, quarter, heightDiff, position, hand, years, club, town, avg, adj, isReal, prov] = s;
    const scores = {} as SkillScores;
    const fair = {} as SkillScores;
    SKILLS.forEach((k, j) => {
      const v = Math.round(avg + (OFFSETS[(i + j) % 6] ?? 0));
      scores[k] = v;
      fair[k] = Math.round(v + adj);
    });
    if (prov) {
      // A provisional player is missing at least one measured skill.
      scores.consistency = null;
      fair.consistency = null;
    }
    const raw = weightedAverage(scores, DEFAULT_WEIGHTS) ?? 0;
    const fairAvg = weightedAverage(fair, DEFAULT_WEIGHTS) ?? 0;
    const bonus = experienceBonus(years);
    const ageAdj = AGE_ADJ[quarter];
    const heightAdj = round1(fairAvg - raw - ageAdj);
    const age_months = GROUP_BASE_MONTHS[group] + (4 - quarter) * 3 + (i % 3) + 12;
    const height_cm = (HEIGHT_AVG[`${gender}-${group}`] ?? 160) + heightDiff;
    return {
      id,
      is_real: isReal,
      name,
      gender,
      age_months: Math.min(age_months, GROUP_BASE_MONTHS[group] + 23),
      age_group: group,
      rank_group: rankGroupLabel(gender, group),
      birth_quarter: quarter,
      height_cm,
      height_diff_cm: heightDiff,
      maturity_offset_years: isReal ? round1(-0.9 + (heightDiff + 8) * 0.1) : null,
      dominant_hand: hand,
      position,
      years_playing: years,
      club,
      town,
      status: prov ? "provisional" : "ranked",
      provisional_reason: prov,
      scores,
      fair_scores: fair,
      experience_bonus: bonus,
      raw_score: round1(raw),
      fair_score: Math.round(fairAvg + bonus),
      score_margin: isReal ? 3 + (i % 2) : 4 + (i % 3),
      raw_rank: null,
      fair_rank: null,
      rank_change: null,
      hidden_gem: false,
      breakdown: [
        { label: "Skill score", value: round1(raw) },
        { label: quarter >= 3 ? "Born late in the year" : "Born early in the year", value: ageAdj },
        { label: heightDiff < 0 ? "Smaller than age average" : "Taller than age average", value: heightAdj },
        { label: "Experience", value: bonus },
      ],
      photo_url: null,
    };
  });
  return rankPlayers(players, DEFAULT_WEIGHTS, { recomputeRaw: true });
}
