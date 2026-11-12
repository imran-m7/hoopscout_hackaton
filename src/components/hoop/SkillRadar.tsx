import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Legend, Tooltip } from "recharts";
import { SKILLS, SKILL_LABELS } from "@/lib/scoring";
import type { SkillScores } from "@/lib/types";

export const SERIES_COLORS = ["var(--primary)", "var(--chart-2)", "var(--chart-3)"];

export function SkillRadar({ series, height = 300 }: { series: { name: string; scores: SkillScores; color?: string | undefined; dashed?: boolean }[]; height?: number }) {
  const data = SKILLS.map((k) => {
    const row: Record<string, string | number> = { skill: SKILL_LABELS[k] };
    series.forEach((s, i) => (row[`s${i}`] = s.scores[k] ?? 0));
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis dataKey="skill" tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        {series.map((s, i) => (
          <Radar
            key={i}
            name={s.name}
            dataKey={`s${i}`}
            stroke={s.color ?? SERIES_COLORS[i % 3]}
            fill={s.color ?? SERIES_COLORS[i % 3]}
            fillOpacity={s.dashed ? 0.05 : 0.25}
            strokeDasharray={s.dashed ? "4 4" : undefined}
            strokeWidth={2}
            isAnimationActive
          />
        ))}
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
