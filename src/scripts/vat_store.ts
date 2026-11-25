/** 큰 기록 저장 — localStorage(약 5MB) 대신 IndexedDB. 5년치 e호조 지출(2만여 건)과 신고서 20장을 합치면 localStorage 한도를 넘어
 *  저장이 조용히 실패하고 다시 열면 빈 화면이 되던 것(운영자 2026-11-25 '전에 올린 것 다시 올릴 필요 없잖아').
 *  들어가면 localStorage 그대로, 넘치면 본문은 IndexedDB 에 두고 localStorage 에는 표시만(지우면 비운 것 — 다른 화면·시험과 같은 뜻). 파일은 밖으로 나가지 않는다 */
const DB = 'vat-store', OS = 'kv';
const open = (): Promise<IDBDatabase> => new Promise((res, rej) => { const r = indexedDB.open(DB, 1); r.onupgradeneeded = () => { if (!r.result.objectStoreNames.contains(OS)) r.result.createObjectStore(OS); }; r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
const tx = async <T>(mode: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> => { const db = await open(); return new Promise((res, rej) => { const t = db.transaction(OS, mode); const s = t.objectStore(OS); const q = f(s); t.oncomplete = () => { res(q ? (q as IDBRequest<T>).result : undefined); db.close(); }; t.onerror = () => { rej(t.error); db.close(); }; }); };
export const idbGet = async (k: string): Promise<string | null> => { try { return (await tx<string>('readonly', s => s.get(k))) ?? null; } catch { return null; } };
export const idbSet = async (k: string, v: string) => { try { await tx('readwrite', s => { s.put(v, k); }); } catch { /* 저장 못 해도 계속 */ } };
export const idbDel = async (k: string) => { try { await tx('readwrite', s => { s.delete(k); }); } catch { /* */ } };
const STUB = '{"v":1,"idb":1}';   /* localStorage 에 남기는 표시 — 본문은 IndexedDB */
/** 읽기 — localStorage 가 기준(지우면 비운 것). 본문이 넘쳐 표시만 있으면 IndexedDB 에서 */
export async function loadBig(k: string): Promise<string | null> {
  let b: string | null = null; try { b = localStorage.getItem(k); } catch { /* */ }
  if (b === STUB) return idbGet(k); if (!b) void idbDel(k); return b;
}
/** 쓰기 — localStorage 에 들어가면 거기, 넘치면 IndexedDB + 표시 */
export function saveBig(k: string, v: string) { try { localStorage.setItem(k, v); void idbDel(k); } catch { void idbSet(k, v); try { localStorage.setItem(k, STUB); } catch { /* */ } } }
export async function saveBigNow(k: string, v: string) { try { localStorage.setItem(k, v); await idbDel(k); } catch { await idbSet(k, v); try { localStorage.setItem(k, STUB); } catch { /* */ } } }
export async function delBig(k: string) { await idbDel(k); try { localStorage.removeItem(k); } catch { /* */ } }
