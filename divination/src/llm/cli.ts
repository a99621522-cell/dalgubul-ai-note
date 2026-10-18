// 터미널에서 질문 하나를 풀어 본다.
//   node src/llm/cli.ts "이번 달 이직 제안을 받아들여도 될까요" [--at 2026-10-18T14:30+09:00] [--lon 128.6] [--numbers 37,58] [--text 대구]
//        [--method both|meihua|qimen|auto] [--year-ming 庚午] [--dry] [--json] [--no-review]
// ANTHROPIC_API_KEY(또는 ant auth login 프로필)가 필요하다. --dry 는 계산만 하고 모델을 부르지 않는다.
import { runDivination, castOnly, type DivinationRequest } from './pipeline.ts';
import { AnthropicCaller } from './model.ts';

function parseArgs(argv: string[]) {
  const out: Record<string, string | boolean> = {};
  const rest: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith('--')) { out[key] = next; i++; } else out[key] = true;
    } else rest.push(a);
  }
  return { flags: out, rest };
}

const { flags, rest } = parseArgs(process.argv.slice(2));
const question = rest.join(' ').trim();
if (!question) { console.error('질문을 적어 주세요. 예: node src/llm/cli.ts "이번 달 이직해도 될까"'); process.exit(2); }

const req: DivinationRequest = {
  question,
  datetime: typeof flags.at === 'string' ? flags.at : undefined,
  longitude: typeof flags.lon === 'string' ? Number(flags.lon) : undefined,
  method: (typeof flags.method === 'string' ? flags.method : 'both') as DivinationRequest['method'],
  yearMing: typeof flags['year-ming'] === 'string' ? flags['year-ming'] : null,
  skipReview: flags['no-review'] === true,
  material: typeof flags.numbers === 'string' ? { numbers: flags.numbers.split(',').map(Number) } : typeof flags.text === 'string' ? { text: flags.text } : undefined,
};

if (flags.dry) {
  console.log(JSON.stringify(castOnly(req, req.method === 'auto' ? 'both' : req.method), null, 1));
  process.exit(0);
}

const caller = new AnthropicCaller();
runDivination(req, caller).then((r) => {
  if (flags.json) { console.log(JSON.stringify(r, null, 1)); return; }
  console.log(r.final);
  console.log('\n---');
  console.log(`분류: ${r.classification.question_type} · ${r.classification.time_horizon} · 안전 ${r.safety.flag} · 술법 ${r.methodUsed}`);
  if (r.review?.changes.length) console.log(`검수 수정: ${r.review.changes.join(' / ')}`);
  console.log(`모델 ${r.model} · 입력 ${r.usage.input} 출력 ${r.usage.output} 캐시읽기 ${r.usage.cacheRead} 캐시쓰기 ${r.usage.cacheWrite} · ${r.elapsedMs}ms`);
}).catch((e) => { console.error(e instanceof Error ? e.message : e); process.exit(1); });
