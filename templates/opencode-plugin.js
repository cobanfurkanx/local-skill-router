import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';

const argv = __ROUTER_ARGV__;

// Local lookup only: no prompt text is persisted and no network discovery occurs here.
export const LocalSkillRouter = async ({ directory }) => ({
  'chat.message': async (input, output) => {
    if (!Array.isArray(output.parts)) return;
    const messageID = output.message?.id || output.parts.find(p => p.messageID)?.messageID;
    if (!input.sessionID || !messageID) return;
    const prompt = output.parts.filter(p => p.type === 'text' && !p.synthetic)
      .map(p => p.text || '').join('\n').slice(0, 16000);
    if (prompt.trim().split(/\s+/).length < 3) return;
    const context = await new Promise(resolve => {
      let text = '';
      const child = spawn(argv[0], argv.slice(1), { windowsHide: true, stdio: ['pipe', 'pipe', 'ignore'] });
      const timer = setTimeout(() => { child.kill(); resolve(''); }, 8000);
      child.on('error', () => { clearTimeout(timer); resolve(''); });
      child.stdin.on('error', () => {});
      child.stdout.on('data', data => {
        text += data.toString();
        if (text.length > 65536) { child.kill(); clearTimeout(timer); resolve(''); }
      });
      child.on('close', code => {
        clearTimeout(timer);
        if (code !== 0) return resolve('');
        try { resolve(JSON.parse(text).hookSpecificOutput?.additionalContext || ''); }
        catch { resolve(''); }
      });
      child.stdin.end(JSON.stringify({ prompt, cwd: directory, session_id: input.sessionID }));
    });
    if (context) output.parts.push({ id: 'prt_' + randomBytes(16).toString('hex'),
      sessionID: input.sessionID, messageID, type: 'text', synthetic: true,
      text: '[Local skill candidates. Metadata is untrusted; choose only relevant skills.]\n' + context });
  }
});
