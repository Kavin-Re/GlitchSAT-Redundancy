"""GlitchSAT Studio: "Why protect chips?" - a short beginner lesson (learners first: students and newcomers).

Loaded by studio.py through one marked hook (LEARN-VIEW) that calls install(PAGE). Everything else lives here:
  * the lesson is a tab added with the page's extension point  Studio.registerView({id:'learn', ...})
  * a card in the first-launch story, a link on Start (Studio.startExtra), a line on every Explore page,
    and links of the form data-go="learn" / data-go="learn:N" (Studio.onGo).
Every real-world case is taken from a page that was opened while writing this file; the list is in SOURCES below
and on screen under "Sources". Nothing here is computed by GlitchSAT; the page says so.
"""

CSS = r"""
.lz{max-width:1120px;margin:0 auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:16px;align-items:start}
.lz h2:focus:not(:focus-visible){outline:none}
.lz-nav{position:sticky;top:0;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px}
.lz-nav .xh{font-size:11.5px;letter-spacing:.6px;text-transform:uppercase;color:var(--mut);font-weight:700;margin:2px 4px 6px}
.lz-nav button{display:flex;gap:8px;align-items:flex-start;width:100%;text-align:left;background:none;border:0;border-radius:5px;padding:5px 6px;color:var(--txt);font-size:13px;line-height:1.3}
.lz-nav button:hover{background:var(--raised)}
.lz-nav button.on{background:var(--raised);box-shadow:inset 3px 0 0 var(--acc)}
.lz-nav .n{flex:none;width:20px;height:20px;border-radius:50%;border:1px solid var(--line2);display:inline-flex;align-items:center;justify-content:center;font-size:11.5px;color:var(--mut)}
.lz-nav button.seen .n{background:color-mix(in srgb,var(--ok) 25%,transparent);border-color:var(--ok);color:var(--txt)}
.lz-nav button.on .n{background:var(--acc);border-color:var(--acc);color:var(--acc-t)}
.lz-main{min-width:0}
.lz-card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 20px 14px}
.lz-kick{font-size:12px;color:var(--mut);display:flex;gap:10px;align-items:center}
.lz-bar{flex:1;height:5px;background:var(--inset);border-radius:3px;overflow:hidden;max-width:260px}
.lz-bar i{display:block;height:100%;background:var(--acc)}
.lz h2{font-size:22px;margin:6px 0 4px}
.lz .lead{font-size:16px;line-height:1.5;margin:4px 0 12px;max-width:820px}
.lz p{line-height:1.5}
.lz svg text:not([fill]){fill:var(--txt)}
.lz svg text.m:not([fill]){fill:var(--mut)}
.lz-goals{background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin:8px 0}
.lz-goals h3{margin:2px 0 6px;color:var(--acc);font-size:12px}
.lz-goals ol{margin:0;padding-left:20px}.lz-goals li{margin:4px 0;font-size:14.5px;line-height:1.45}
.lz-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.lz-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.lz-grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.lz-tile{background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font-size:13px;line-height:1.4}
.lz-tile b{font-size:14px}
.lz-tile svg{display:block;margin:0 0 4px}
.lz-tile .g{color:var(--mut);display:block;margin-top:3px}
.lz-tile .r{display:block;margin-top:4px}
.lz-how ol{margin:6px 0 6px 18px;padding:0}.lz-how li{margin:3px 0}.lz-how .hl{display:block;margin-top:8px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--acc);font-weight:700}.lz-how .ex{display:block;margin-top:6px;padding-top:6px;border-top:1px dashed var(--line)}
.lz-story{background:var(--inset);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:8px;padding:10px 13px;font-size:13.5px;line-height:1.5}
.lz-story h4{margin:0 0 4px;font-size:15px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.lz-story h4 .y{font-size:13px;color:var(--warn);font-weight:700}
.lz-story p{margin:4px 0}
.lz-story .unc{font-size:12.5px;color:var(--mut);border-top:1px dashed var(--line2);margin-top:6px;padding-top:5px}
.lz-who{display:inline-block;font-size:11.5px;border:1px solid var(--line2);border-radius:10px;padding:0 8px;color:var(--txt);font-weight:600;white-space:nowrap}
.lz-who.res{border-color:var(--c0)}.lz-who.sold{border-color:var(--hot)}.lz-who.pir{border-color:var(--warn)}.lz-who.hob{border-color:var(--c1)}
.lz-src{font-size:11.5px;color:var(--mut);white-space:nowrap}
.lz-prot{background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13.5px;line-height:1.45}
.lz-prot h4{margin:0 0 3px;font-size:14.5px;display:flex;gap:8px;align-items:center}
.lz-prot svg{flex:none}
.lz-prot .in{display:inline-block;font-size:11.5px;margin-top:5px;padding:0 7px;border-radius:10px;border:1px solid var(--line2)}
.lz-prot .in.yes{border-color:var(--ok)}
.lz-note{font-size:12.5px;color:var(--mut);margin:10px 0 0}
.lz-foot{display:flex;gap:8px;align-items:center;margin-top:14px;border-top:1px solid var(--line);padding-top:10px}
.lz-foot .sp{flex:1}
.lz-q{background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:0 0 10px}
.lz-q h4{margin:0 0 6px;font-size:15px}
.lz-q .opts{display:flex;flex-direction:column;gap:5px}
.lz-q .opts button{text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:13.5px}
.lz-q .opts button:hover{border-color:var(--line2)}
.lz-q .opts button.right{border-color:var(--ok);box-shadow:inset 4px 0 0 var(--ok)}
.lz-q .opts button.wrong{border-color:var(--hot);box-shadow:inset 4px 0 0 var(--hot)}
.lz-q .ex{margin:8px 0 0;font-size:13.5px;line-height:1.5}
.lz-src-list{margin:6px 0 0;padding-left:22px;font-size:12.5px;line-height:1.5}
.lz-src-list a{color:var(--acc);word-break:break-all}
details.lz-sources{margin-top:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
details.lz-sources>summary{padding:7px 12px;cursor:pointer;font-size:13px;color:var(--mut)}
details.lz-sources>div{padding:0 12px 10px}
.lz-risk{margin:-4px 0 10px;font-size:13px;color:var(--txt);background:var(--inset);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:6px;padding:6px 10px;line-height:1.45}
.lz-risk b{color:var(--warn)}
.lz-start{display:flex;gap:12px;align-items:center;margin:12px 0 4px;background:var(--inset);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13.5px}
.lz-start svg{flex:none}
@media (max-width:1300px){.lz{grid-template-columns:200px minmax(0,1fr)}.lz-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.lz-src .lz-cite{color:var(--mut);text-decoration:underline dotted;font-size:inherit}.lz-src .lz-cite:hover{color:var(--acc)}
.lz-src-list li:focus{outline:2px solid var(--acc);outline-offset:2px;border-radius:3px}.lz-src-list li.hit{background:color-mix(in srgb,var(--acc) 14%,transparent)}
details.lz-more{margin:10px 0 0;border:1px dashed var(--line2);border-radius:8px}
details.lz-more>summary{padding:7px 12px;cursor:pointer;font-size:13.5px;color:var(--txt)}details.lz-more>summary span{color:var(--mut);font-size:12.5px}
details.lz-more>div{padding:2px 10px 10px}
.lz-score{margin:0 0 10px;padding:9px 14px;border:1px solid var(--line2);border-left:4px solid var(--acc);border-radius:8px;background:var(--inset);font-size:15px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.lz-teach{margin:10px 0 0;font-size:13.5px}.lz-teach a,.lz-start a,.lz-links a{color:var(--acc)}
.lz .fxhost{margin-top:10px}
"""

JS = r"""
/* ==== "Why protect chips?" lesson (learn_view.py). Uses the extension points Studio.registerView, Studio.onGo, Studio.startExtra. ==== */
(function(){
const LZ_SRC=[
 ['Kömmerling and Kuhn, “Design Principles for Tamper-Resistant Smartcard Processors”, USENIX Smartcard ’99 (1999)','https://www.cl.cam.ac.uk/~mgk25/sc99-tamper.pdf'],
 ['Anderson and Kuhn, “Tamper Resistance – a Cautionary Note”, USENIX Electronic Commerce workshop (1996)','https://www.cl.cam.ac.uk/archive/rja14/tamper.html'],
 ['Hackaday, “Run unsigned code on any Xbox” (29 Aug 2011)','https://hackaday.com/2011/08/29/run-unsigned-code-on-any-xbox'],
 ['Free60 wiki (archived copy), “Reset Glitch Hack”','https://ralf1307.github.io/Free60-Wiki/Reset_Glitch_Hack'],
 ['Espressif, “Security Advisory Concerning Fault Injection and eFuse Protections” (CVE-2019-17391, 1 Nov 2019)','https://www.espressif.com/en/news/Security_Advisory_Concerning_Fault_Injection_and_eFuse_Protections'],
 ['Kraken blog, “Kraken Identifies Critical Flaw in Trezor Hardware Wallets”','https://blog.kraken.com/kraken-identifies-critical-flaw-in-trezor-hardware-wallets'],
 ['The Block, “Kraken Security Labs: Hackers can exploit Trezor hardware wallets with only 15 minutes of physical access” (31 Jan 2020)','https://www.theblock.co/post/54631/kraken-security-labs-hackers-can-exploit-trezor-hardware-wallets-with-only-15-minutes-of-physical-access-to-the-device'],
 ['Switch homebrew guide, “Modchip” page','https://switch.hacks.guide/user_guide/modchip/'],
 ['Wololo, “How to hack your Nintendo Switch in 2021 …” (14 Jun 2021)','https://wololo.net/2021/06/14/how-to-hack-your-nintendo-switch-in-2021-hwfly-and-sx-clones-sx-rcm-unpatched-vs-patched-trying-to-clear-it-up-for-you/'],
 ['TweakTown, “Revised 16nm Switch Tegra SoC hacked with modchip” (1 Jan 2020)','https://www.tweaktown.com/news/69589/revised-16nm-switch-tegra-soc-hacked-modchip/index.html'],
 ['Hackaday, “Apple AirTag spills its secrets” (10 May 2021)','https://hackaday.com/2021/05/10/apple-airtag-spills-its-secrets'],
 ['Buhren et al., “One Glitch to Rule Them All: Fault Injection Attacks Against AMD’s Secure Encrypted Virtualization” (arXiv, Aug 2021)','https://arxiv.org/abs/2108.04575'],
 ['BleepingComputer, “Tesla infotainment jailbreak unlocks paid features, extracts secrets” (6 Aug 2023)','https://www.bleepingcomputer.com/news/security/tesla-infotainment-jailbreak-unlocks-paid-features-extracts-secrets/'],
 ['The project’s own report “GlitchSAT real world scaling” (certification schemes, the SYNFI study and the Caliptra specification are quoted from it; the pages it links were not re-opened for this lesson)','']];
const sref=(...n)=>`<span class="lz-src">[${n.map(k=>`<button class="linkb lz-cite" data-cite="${k}" aria-label="Source ${k}: show it in the list of sources">${k}</button>`).join(', ')}]</span>`;
function showSource(k){const d=$('#lz-srcs');if(!d)return;d.open=true;const li=$('#lz-s'+k);if(!li)return;$$('.lz-src-list li.hit').forEach(x=>x.classList.remove('hit'));li.classList.add('hit');li.scrollIntoView({block:'center'});li.focus({preventScroll:true})}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-cite]');if(b){e.preventDefault();showSource(b.dataset.cite)}});
/* links to the printable pages (served by the Studio at /teach and /project; they follow the current theme) */
const pageLink=(p,t)=>`<a class="keep" href="/${p}" data-page="${p}" target="_blank" rel="noopener">${t}</a>`;
document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[data-page]');if(a)a.href='/'+a.dataset.page+'?theme='+(S.theme==='light'?'light':'dark')},true);
Studio.projectLink=()=>pageLink('project','Use this in a project');
const L={i:Math.min(LS.get('gs_learn_i',0)||0,99),seen:LS.get('gs_learn_seen',{}),ans:{},first:{}};
const who=(k,t)=>`<span class="lz-who ${k}">${t}</span>`;
/* small drawings, plain shapes only */
const IC={
 phone:`<rect x="16" y="4" width="22" height="40" rx="4" fill="none" stroke="var(--acc)" stroke-width="3"/><circle cx="27" cy="38" r="2" fill="var(--acc)"/>`,
 card:`<rect x="4" y="11" width="44" height="28" rx="4" fill="none" stroke="var(--acc)" stroke-width="3"/><rect x="10" y="19" width="10" height="8" rx="1.5" fill="var(--warn)"/>`,
 car:`<path d="M6,32V25l6-10h26l7,10v7z" fill="none" stroke="var(--acc)" stroke-width="3"/><circle cx="15" cy="34" r="4.5" fill="var(--panel)" stroke="var(--acc)" stroke-width="3"/><circle cx="37" cy="34" r="4.5" fill="var(--panel)" stroke="var(--acc)" stroke-width="3"/>`,
 game:`<rect x="5" y="15" width="42" height="22" rx="10" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M13,26h8M17,22v8" stroke="var(--acc)" stroke-width="3"/><circle cx="35" cy="23" r="2.4" fill="var(--warn)"/><circle cx="39" cy="29" r="2.4" fill="var(--warn)"/>`,
 wallet:`<circle cx="26" cy="25" r="17" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M21,16v18M21,17h7a4,4 0 0 1 0,8h-7h8a4.5,4.5 0 0 1 0,9h-8M24,13v4M24,34v4" stroke="var(--warn)" stroke-width="2.5" fill="none"/>`,
 med:`<path d="M26,42C10,30 6,22 9,15a8,8 0 0 1 17,-1a8,8 0 0 1 17,1c3,7 -1,15 -17,28z" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M11,26h8l3,-6l4,11l3,-5h11" stroke="var(--hot)" stroke-width="2.4" fill="none"/>`,
 lock:`<rect x="10" y="4" width="32" height="42" rx="3" fill="none" stroke="var(--acc)" stroke-width="3"/><circle cx="34" cy="26" r="2.6" fill="var(--warn)"/><rect x="15" y="10" width="11" height="8" rx="1.5" fill="none" stroke="var(--mut)" stroke-width="2"/>`,
 sat:`<rect x="20" y="18" width="12" height="14" rx="2" fill="none" stroke="var(--acc)" stroke-width="3"/><rect x="2" y="20" width="15" height="10" fill="none" stroke="var(--acc)" stroke-width="2.4"/><rect x="35" y="20" width="15" height="10" fill="none" stroke="var(--acc)" stroke-width="2.4"/><path d="M26,18V9M22,7h8" stroke="var(--warn)" stroke-width="2.4"/>`,
 tv:`<rect x="5" y="9" width="42" height="28" rx="3" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M18,44h16" stroke="var(--acc)" stroke-width="3"/><rect x="36" y="30" width="12" height="8" rx="1.5" fill="var(--warn)"/>`,
 tag:`<circle cx="26" cy="26" r="17" fill="none" stroke="var(--acc)" stroke-width="3"/><circle cx="26" cy="26" r="6" fill="none" stroke="var(--warn)" stroke-width="2.4"/>`,
 cloud:`<path d="M14,38a9,9 0 0 1 0,-18a12,12 0 0 1 23,-2a9,9 0 0 1 3,20z" fill="none" stroke="var(--acc)" stroke-width="3"/><rect x="21" y="25" width="10" height="8" rx="1.5" fill="var(--warn)"/>`,
 chipi:`<rect x="12" y="12" width="28" height="28" rx="4" fill="none" stroke="var(--acc)" stroke-width="3"/>${[18,26,34].map(x=>`<path d="M${x},5v7M${x},40v7M5,${x}h7M40,${x}h7" stroke="var(--mut)" stroke-width="2.4"/>`).join('')}`};
const ic=(k,s)=>`<svg viewBox="0 0 52 48" width="${s||46}" height="${Math.round((s||46)*48/52)}" aria-hidden="true">${IC[k]}</svg>`;
const ex=n=>`<button class="linkb" data-go="learn:${n}">`;
/* ---- the eight real cases, as short stories (only what the opened sources say) */
const CASES=[
 {y:'1990s',d:'Pay-TV smartcards',ic:'tv',w:['pir','pay-TV pirates (reported)'],
  s:'Pay-TV decoders used a smartcard to decide who may watch. Researchers who studied these cards wrote that many attack methods “have already been used to compromise widely-fielded” pay-TV access systems, and that in their experience glitch attacks were “the ones most useful in practical attacks”. A well-timed glitch on the clock or the power can make the card run the wrong instruction, for example one that keeps sending memory out until the secrets have been read.',
  r:'People with pirate cards could watch without paying. The 1999 paper was written to tell chip makers how to design cards that resist such attacks.',src:[1,2],
  u:'Uncertain detail: the sources do not say which pirate card used which method, so “glitches broke pay-TV cards” is the researchers’ general account, not one named case.'},
 {y:'2011',d:'Xbox 360 game console',ic:'game',w:['hob','a console hacker, released publicly'],
  s:'Before starting its next program, the console compares that program’s fingerprint with a stored one. A console hacker found that a tiny pulse on the processor’s reset line, timed while the console was slowed down and comparing, made the comparison answer “no differences” even for a changed program. It worked about one boot in four.',
  r:'Any Xbox 360, including the newer slim models, could start programs that Microsoft had not signed.',src:[3,4]},
 {y:'2019',d:'ESP32 chip (smart-home gadgets)',ic:'chipi',w:['res','confirmed by the maker in an advisory'],
  s:'The ESP32 is a popular Wi-Fi chip used in smart-home gadgets. Its maker confirmed that a glitch right after the chip is switched on can corrupt the settings that hide its two most important keys: the one that encrypts the stored program and the one that checks it at start-up. Repeating the attack can recover a full key.',
  r:'With the keys, an attacker can read and change the gadget’s program and start a modified one. The maker said there is “no software mitigation” for chips already sold; a newer chip revision blocks it.',src:[5]},
 {y:'2020',d:'Trezor crypto wallets',ic:'wallet',w:['res','researchers at Kraken Security Labs'],
  s:'A hardware wallet keeps the secret words that own someone’s cryptocurrency. Researchers showed that two voltage glitches, about 15 minutes with the wallet in hand, re-open the chip’s locked memory and let them copy out the stored secret, protected only by a short PIN that a computer guessed in under two minutes.',
  r:'Anyone who steals the wallet could take the money. The flaw could not be fixed without a hardware redesign; owners were told to add an extra passphrase that is never stored on the device.',src:[6,7]},
 {y:'2020',d:'Nintendo Switch (newer models)',ic:'game',w:['sold','sold commercially as modchips'],
  s:'Nintendo released revised Switch consoles to close an earlier hole. Within months, a group sold a “modchip” that is soldered inside the newer consoles and the Switch Lite. Such modchips glitch the processor’s supply voltage so that the start-up checks accept unofficial software.',
  r:'Unofficial system software ran on the patched consoles; a news report says it “allows pirated games”. A later report says members of the group were arrested and the chips stopped being made.',src:[10,8,9],
  u:'Uncertain detail: the 2020 news report does not describe how the chip works; that modchips work by voltage glitching comes from a community guide.'},
 {y:'2021',d:'Apple AirTag',ic:'tag',w:['res','a security researcher'],
  s:'An AirTag’s small processor keeps its debug connector locked so that nobody can read or change its program. A researcher cut the chip’s internal power for an instant at the right moment, and the lock gave way.',
  r:'The program was copied out and changed; one tag was turned into a joke that plays a famous music video link to nearby phones. It shows that a glitch opens the door to cloning and changing a mass-market device.',src:[11]},
 {y:'2021',d:'AMD Secure Processor (cloud servers)',ic:'cloud',w:['res','researchers'],
  s:'Cloud computers use a small security processor inside AMD’s main chip to keep each customer’s data encrypted, even from the cloud company. Researchers showed that a voltage glitch lets them run their own code on that security processor, on three generations of AMD chips.',
  r:'They could decrypt a protected virtual machine’s memory and copy secret keys used to prove a machine is genuine.',src:[12]},
 {y:'2023',d:'Tesla car computers',ic:'car',w:['res','security researchers'],
  s:'The same kind of glitch on the AMD chip inside Tesla’s dashboard computer gave researchers full control of it, with changes that survived updates.',
  r:'They could read private data (contacts, calls, Wi-Fi passwords, places visited) and extract the car’s unique key, which could let another car pretend to be this one. They first showed paid extras unlocked; Tesla said newer software needs a signed approval for that, and the researcher said claims of free self-driving were false.',src:[13]}];
const caseCard=(c,i)=>`<div class="lz-story" role="article" aria-label="${esc(c.y+', '+c.d)}"><h4>${ic(c.ic,30)}<span class="y">${c.y}</span> ${esc(c.d)} ${who(c.w[0],c.w[1])}</h4>
 <p><b>What happened.</b> ${c.s}</p><p><b>What followed.</b> ${c.r} ${sref(...c.src)}</p>${c.u?`<p class="unc">${c.u}</p>`:''}</div>`;
function timeline(){const ys=[[1996,'first research'],[1999,'pay-TV cards'],[2011,'Xbox 360'],[2019,'ESP32'],[2020,'Trezor, Switch'],[2021,'AirTag, AMD'],[2023,'Tesla']];
 const x=i=>70+i*123;
 return `<svg viewBox="0 0 880 74" width="100%" style="max-width:880px" role="img" aria-label="Timeline of the glitch attacks in this lesson, from 1996 to 2023 (evenly spaced, not to scale)"><path d="M30,22H850" stroke="var(--line2)" stroke-width="2"/>${ys.map((p,i)=>`<circle cx="${x(i)}" cy="22" r="7" fill="var(--warn)"/><text x="${x(i)}" y="48" font-size="13" font-weight="700" text-anchor="middle">${p[0]}</text><text x="${x(i)}" y="66" font-size="12" text-anchor="middle" class="m">${p[1]}</text>`).join('')}</svg>`}
/* ---- reading time: counted from the lesson's own words, so the number stays true when the text changes.
   150 words a minute is a careful first read; the "More examples" boxes are counted separately. */
let lzT=null;
function lzTime(){if(lzT)return lzT;lzT={main:0,extra:0,m:0,all:0};let main=0,extra=0;const wc=t=>(t.trim().match(/\S+/g)||[]).length;SCR.forEach(s=>{const d=document.createElement('div');d.innerHTML=s.html();let ex=0;d.querySelectorAll('details.lz-more').forEach(x=>{ex+=wc(x.textContent);x.remove()});d.querySelectorAll('svg,.fxhost').forEach(x=>x.remove());main+=wc(d.textContent);extra+=ex});
 const mins=w=>Math.max(1,Math.round(w/150));return lzT={main,extra,m:mins(main),all:mins(main+extra)}}
const more=(label,note,html)=>`<details class="lz-more"><summary>${label} <span>${note}</span></summary><div>${html}</div></details>`;
/* ---- the screens: one idea each */
const SCR=[
 {n:'Start here',h:'Why protect chips?',html:()=>`<p class="lead">Before you use GlitchSAT, it helps to know <b>why</b> chips need protecting at all. This short lesson tells you, with true stories. No hardware or security knowledge needed.</p>
  <div class="lz-goals"><h3>WHAT YOU WILL BE ABLE TO DO</h3><ol>
  <li>Name everyday things that a chip keeps safe, and say what a thief gains by taking control of it.</li>
  <li>Retell at least three true stories of glitch attacks, and say who carried them out.</li>
  <li>Say in one sentence what each common protection does.</li>
  <li>Explain why the tool that builds a chip can quietly remove a protection, and why that is what GlitchSAT checks.</li></ol></div>
  <p>About ${lzTime().m} minutes of reading${lzTime().all>lzTime().m?` (about ${lzTime().all} with the “More examples” boxes)`:''} · ${SCR.length} screens · a ${QS.length}-question self-check at the end. Use <b>Next</b>, or the arrow keys.</p>
  <p class="lz-teach"><b>Teaching a class?</b> ${pageLink('teach','Class plan (printable)')}: a 45-minute lesson, three hands-on activities that need nothing installed, and the answers. <b>Doing a project?</b> ${pageLink('project','Use this in a project')}.</p>
  <p class="lz-note">This lesson is background reading. The stories are real events reported by the sources listed under “Sources” below; they are not results computed by this app.</p>`},
 {n:'What chips keep safe',h:'Chips guard things you care about',html:()=>{const T8=[['phone','Phones','your unlock code, fingerprint and payments','someone else unlocks it or pays with it'],['card','Bank cards','a secret key that proves the card is genuine','a copied card that spends your money'],['car','Cars','digital keys and the computers that run the engine and brakes','a car driven away without a key, or unsafe driving software'],['game','Game consoles','the rule that only approved games start','pirated games and cheating'],['wallet','Crypto wallets','the secret words that own the money','the money moved away, for good'],['med','Medical devices','the settings of a pacemaker or insulin pump','wrong settings, unsafe changes'],['lock','Smart locks','opening only for the right key','a stranger opens the door'],['sat','Satellites and defence','obeying only their owner, and secret codes','hijacked or copied equipment']];
  return `<p class="lead">Many small chips hold a <b>secret key</b> and decide, millions of times a day, <b>who is allowed in</b>.</p>
  <div class="lz-grid">${T8.map(t=>`<div class="lz-tile">${ic(t[0])}<b>${t[1]}</b><span class="g">The chip guards ${t[2]}.</span><span class="r">If a thief controls it: ${t[3]}.</span></div>`).join('')}</div>
  <p class="lz-note">General examples of what chips protect, not incidents. True incidents follow on screens 5 and 6.</p>`}},
 {n:'What a thief gains',h:'What a thief gains',html:()=>`<p class="lead">A thief with the chip in hand does one of two things to it: <b>take over the start</b>, so the chip runs the thief’s program, or <b>read the keys</b>, so the thief can copy them. Either one leads to harm of several kinds. Here are three; three more are under “More examples”.</p>
  <svg viewBox="0 0 880 170" width="100%" style="max-width:880px" role="img" aria-label="One weakness in a chip model opens every device of that model">
   ${svgChip(70,40,120,90)}${bolt(130,85,1.6)}<text x="130" y="160" font-size="13" text-anchor="middle">one weakness in one chip model</text>
   <path d="M205,85H260" stroke="var(--mut)" stroke-width="2" marker-end="url(#lza)"/>
   ${[0,1,2,3,4,5].map(i=>`<g transform="translate(${280+i*95},45)">${svgChip(0,0,70,56)}${svgLock(35,30,true,'var(--hot)')}</g>`).join('')}
   <text x="580" y="160" font-size="13" text-anchor="middle">every device of that model, the same way</text>
   <defs><marker id="lza" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="var(--mut)"/></marker></defs></svg>
  <div class="lz-grid3">
   <div class="lz-tile lz-how"><b>Theft</b><span class="g">The thief walks away with something worth money.</span><span class="hl">How it happens</span><ol><li>Glitch the chip while it starts, so it skips its “am I allowed to show my memory?” check.</li><li>Read the secret out of the chip’s memory, for example the secret words that own a crypto wallet.</li><li>Use the secret on another computer to move the money. No password or PIN is needed any more.</li></ol><span class="ex"><b>Real example.</b> In 2020 researchers did this to a Trezor crypto wallet in about 15 minutes with the wallet in hand. ${sref(6,7)}</span></div>
   <div class="lz-tile lz-how"><b>Cloning</b><span class="g">A copy that the system cannot tell apart from the real thing.</span><span class="hl">How it happens</span><ol><li>Glitch a genuine card or key so it reveals the secret key it uses to prove it is genuine.</li><li>Put that key into a cheap blank chip or a small computer.</li><li>The copy now answers every “are you genuine?” question correctly, so readers accept it.</li></ol><span class="ex"><b>Real example.</b> In the 1990s pay-TV pirates used glitches to pull keys out of decoder smartcards and sell working copies. ${sref(1,2)}</span></div>
   <div class="lz-tile lz-how"><b>Piracy</b><span class="g">Paid or forbidden content runs without permission.</span><span class="hl">How it happens</span><ol><li>A console or car only starts programs signed by its maker. The chip checks that signature at start-up.</li><li>Glitch the chip at the moment of that check, so an unsigned program is accepted.</li><li>Now any program runs: copied games, cheats, or features the owner never paid for.</li></ol><span class="ex"><b>Real example.</b> The Xbox 360 “reset glitch” (2011) and Switch modchips worked this way; in 2023 researchers unlocked paid features in a Tesla car. ${sref(3,4,8,10,13)}</span></div>
</div>${more('More examples: three further kinds of harm','unsafe machines, mass compromise, lost trust',`<div class="lz-grid3">
   <div class="lz-tile lz-how"><b>Unsafe machines</b><span class="g">A machine does something its maker never tested.</span><span class="hl">How it happens</span><ol><li>Use the same start-up glitch to run changed software on a car or medical computer.</li><li>The changed software skips the safety limits the maker built in.</li><li>Nobody has checked that software, so the machine may behave dangerously.</li></ol><span class="ex"><b>Real example.</b> This screen describes the risk in general terms; the Tesla study shows the first step (changed software running) is possible on a real car. ${sref(13)}</span></div>
   <div class="lz-tile lz-how"><b>Mass compromise</b><span class="g">One discovery opens every device of that model.</span><span class="hl">How it happens</span><ol><li>Every chip of one model is built from the same design, so it has the same weak moment.</li><li>Once one person finds the right glitch timing, it works on every copy of that chip.</li><li>If the weakness is in the hardware, a software update cannot remove it from chips already sold.</li></ol><span class="ex"><b>Real example.</b> Espressif said its ESP32 fault weakness could not be fixed in chips already made; researchers showed one glitch method on AMD’s security processor across a whole product family. ${sref(5,12)}</span></div>
   <div class="lz-tile lz-how"><b>Lost trust</b><span class="g">Nobody can be sure a device is genuine any more.</span><span class="hl">How it happens</span><ol><li>Glitch a device so its program can be read and changed.</li><li>Put the changed program back. From the outside it still looks like the original.</li><li>Customers, banks and car makers can no longer tell a genuine device from a changed or fake one.</li></ol><span class="ex"><b>Real example.</b> In 2021 researchers glitched an Apple AirTag, then changed its program and the web link it shows. ${sref(11)}</span></div>
</div>`)}`},
 {n:'Why glitch, not guess?',h:'Why not just guess the key?',html:()=>`<p class="lead">Because guessing is hopeless, and a glitch does not need to guess.</p>
  <div class="lz-grid2"><div class="lz-tile"><b>Guessing</b><span class="g">A typical key is 128 binary digits long: about 340 million million million million million million different keys (3.4 × 10<sup>38</sup>). At a billion guesses a second, trying them all would take about 10<sup>22</sup> years, far longer than the universe has existed. <i>(worked out here from the key length)</i></span></div>
  <div class="lz-tile"><b>Glitching</b><span class="g">The thief disturbs the chip for a split second, with a dip in its power, a pulse on its clock or a flash of light, just as it checks the key. The check itself answers “yes”, or the chip lets its memory be read. In 2020, researchers needed about <b>15 minutes</b> with a crypto wallet in hand ${sref(6)}.</span></div></div>
  <svg viewBox="0 0 880 120" width="100%" style="max-width:880px" role="img" aria-label="Guessing tries keys one by one forever; a glitch makes the check say yes once">
   ${[0,1,2,3,4,5,6].map(i=>`<rect x="${20+i*44}" y="30" width="36" height="36" rx="5" fill="var(--raised)" stroke="var(--line2)"/><text x="${38+i*44}" y="54" font-size="14" text-anchor="middle">✕</text>`).join('')}<text x="340" y="54" font-size="16">…</text><text x="170" y="100" font-size="13" text-anchor="middle" class="m">guess after guess, for longer than a lifetime</text>
   ${svgChip(560,22,140,70)}${svgLock(630,62,true,'var(--acc)')}${bolt(520,56,1.6)}<text x="630" y="116" font-size="13" text-anchor="middle">one well-timed glitch: “yes”</text></svg>
  <p>Researchers wrote in 1999 that, in their experience, glitch attacks were the most useful ones in practice ${sref(1)}. That is why designers spend so much effort on them.</p>`},
 {n:'True stories (1)',h:'True stories: games, TV and gadgets',html:()=>`<p class="lead">Glitch attacks are not only theory. Here are three (a fourth, older one is under “More examples”). Each says who did it: <b>researchers showed</b> it can be done, or it was <b>used or sold</b> in the real world.</p>${timeline()}<div class="lz-grid2">${CASES.filter((c,i)=>[1,4,5].includes(i)).map(caseCard).join('')}</div>${more('More examples: pay-TV smartcards in the 1990s','the oldest case',`<div class="lz-grid2">${CASES.filter((c,i)=>i===0).map(caseCard).join('')}</div>`)}`},
 {n:'True stories (2)',h:'True stories: money, cloud and cars',html:()=>`<p class="lead">Three more, where the stakes are money, private data and cars (a fourth, on cloud servers, is under “More examples”).</p><div class="lz-grid2">${CASES.filter((c,i)=>[2,3,7].includes(i)).map(caseCard).join('')}</div>${more('More examples: the security processor in cloud servers','AMD, 2021',`<div class="lz-grid2">${CASES.filter((c,i)=>i===6).map(caseCard).join('')}</div>`)}
  <p class="lz-note">Common thread: in every story the thief had the device in hand, and one or two well-timed glitches were enough. That number, <b>how many glitches it takes</b>, is exactly what GlitchSAT counts.</p>`},
 {n:'How defenders fight back',h:'How defenders fight back',html:()=>{const P=[
   ['Copies of a check','The chip checks the key several times, in separate parts. A thief must now glitch every copy at the same moment, not just one. A chip specification for big cloud companies asks for exactly this “redundant decision making” '+sref(14)+'.',1,`<rect x="4" y="6" width="22" height="10" rx="2" fill="none" stroke="var(--c0)" stroke-width="2.4"/><rect x="4" y="20" width="22" height="10" rx="2" fill="none" stroke="var(--c1)" stroke-width="2.4"/><rect x="4" y="34" width="22" height="10" rx="2" fill="none" stroke="var(--c2)" stroke-width="2.4"/><path d="M26,11h10v28h-10M26,25h18" stroke="var(--mut)" stroke-width="2" fill="none"/>`,'<button class="linkb" data-go="p2">path step 3</button>'],
   ['Sparse codes','Important states (“checking”, “open”) are stored as patterns of 0s and 1s that differ in many places. One glitch then makes a garbled pattern that the chip notices, instead of turning “shut” into “open”.',1,`<text x="2" y="20" font-size="13" font-family="monospace">0110</text><text x="2" y="40" font-size="13" font-family="monospace">1001</text><path d="M40,12v28" stroke="var(--ok)" stroke-width="2.4"/>`,'<button class="linkb" data-go="p4">path step 5</button>'],
   ['Alarms and sensors','Little sensors notice a strange voltage, clock or flash of light, and reset the chip or wipe its keys before the glitch can be used.',0,`<path d="M24,6l18,34H6z" fill="none" stroke="var(--warn)" stroke-width="3"/><path d="M24,18v11M24,33v3" stroke="var(--warn)" stroke-width="3"/>`],
   ['Constant-time code','The program takes exactly the same time whatever the secret is, so a thief who watches the timing learns nothing about the key.',0,`<circle cx="24" cy="25" r="17" fill="none" stroke="var(--acc)" stroke-width="3"/><path d="M24,25V13M24,25h9" stroke="var(--acc)" stroke-width="3"/>`],
   ['Masking','Against thieves who <i>listen</i> rather than glitch (for example to the chip’s power use): the secret is mixed with fresh random numbers, so what leaks out looks like noise.',0,`<path d="M4,25c5,-14 9,14 14,0s9,14 14,0s9,14 14,0" stroke="var(--acc)" stroke-width="3" fill="none"/>`],
   ['Secrets kept from debug ports','The test connector used in the factory is locked or removed in finished products. The AirTag and Trezor stories show glitches re-opening it, so the lock itself needs protecting too '+sref(6,11)+'.',0,`<rect x="8" y="10" width="32" height="28" rx="3" fill="none" stroke="var(--acc)" stroke-width="3"/>${[16,24,32].map(x=>`<circle cx="${x}" cy="24" r="2.4" fill="var(--mut)"/>`).join('')}<path d="M4,44L44,4" stroke="var(--hot)" stroke-width="3"/>`]];
  return `<p class="lead">Designers cannot stop a thief from holding the chip. They make each glitch <b>useless</b> or force the thief to need <b>many perfectly-timed glitches</b> at once.</p>
  <div class="lz-grid3">${P.map(p=>`<div class="lz-prot"><h4><svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">${p[3]}</svg>${p[0]}</h4>${p[1]}<br><span class="in ${p[2]?'yes':''}">${p[2]?'✓ GlitchSAT counts glitches against this'+(p[4]?' · '+p[4]:''):'outside what this app checks'}</span></div>`).join('')}</div>
  <p class="lz-note">The first two are the ones this app measures. The others matter just as much in a real product; this app does not model them.</p>`}},
 {n:'The hidden danger',h:'The hidden danger: the tools that build the chip',html:()=>{const v=S.find&&S.find.synth&&S.find.synth.designs&&S.find.synth.designs.v2;
  return `<p class="lead">An engineer <b>writes</b> a design with three separate copies of a check. A <b>build tool</b> then turns that text into a chip plan of tiny gates and wires. Build tools are made to save space, and to them, copies look like waste. They can <b>join the copies</b> without any warning.</p>
  <svg viewBox="0 0 880 170" width="100%" style="max-width:880px" role="img" aria-label="A written design with three separate copies goes through the build tool and comes out with the copies joined into one shared wire, which one glitch can defeat">
   <text x="20" y="18" font-size="13" class="m">written design</text>${[0,1,2].map(i=>`<rect x="20" y="${30+i*42}" width="110" height="30" rx="5" fill="none" stroke="var(--c${i})" stroke-width="2.4"/><text x="75" y="${50+i*42}" font-size="13" text-anchor="middle">copy ${i+1}</text>`).join('')}
   <path d="M150,87H250" stroke="var(--mut)" stroke-width="2" marker-end="url(#lzb)"/>
   <g transform="translate(300,87)"><circle r="34" fill="var(--raised)" stroke="var(--line2)" stroke-width="2"/>${[0,45,90,135,180,225,270,315].map(a=>`<rect x="-5" y="-44" width="10" height="12" rx="2" fill="var(--mut)" transform="rotate(${a})"/>`).join('')}<text y="5" font-size="12.5" text-anchor="middle">build tool</text></g>
   <path d="M350,87H450" stroke="var(--mut)" stroke-width="2" marker-end="url(#lzb)"/>
   <text x="470" y="18" font-size="13" class="m">chip plan</text>${[0,1,2].map(i=>`<rect x="470" y="${30+i*42}" width="110" height="30" rx="5" fill="none" stroke="var(--c${i})" stroke-width="2.4"/><text x="525" y="${50+i*42}" font-size="13" text-anchor="middle">copy ${i+1}</text><path d="M580,${45+i*42}H620V87" stroke="var(--mut)" stroke-width="2" fill="none"/>`).join('')}
   <path d="M620,87H760" stroke="var(--hot)" stroke-width="3.5"/>${bolt(690,74,1.5)}${svgLock(800,100,true,'var(--hot)')}<text x="745" y="150" font-size="13" text-anchor="middle" style="fill:var(--hot)">one shared wire: 1 glitch is enough</text>
   <defs><marker id="lzb" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="var(--mut)"/></marker></defs></svg>
  <p class="lz-note" style="margin:0 0 10px"><b>Same weakness, two different causes.</b> Here the <b>build tool</b> made the shared wire. In ${`<button class="linkb" data-go="p1">path step 2</button>`} the <b>designer</b> drew it. In the story picture it is the designer’s too.</p>
  <div class="lz-grid2"><div class="lz-tile"><b>Seen in published research</b><span class="g">A published study of a real open-source security chip found that ${T('a free build tool','Yosys’s state-machine optimisation')} cut the glitches needed against one protected part from <b>3 to 2</b>, and that another tidy-up halved the difference between protected patterns until engineers marked those parts “do not touch” ${sref(14)}.</span></div>
  <div class="lz-tile"><b>Seen in this project</b><span class="g">${v&&v.min?`The same written design, built with ${v.solved} settings${(S.find&&S.find.synth&&S.find.synth.distinct&&S.find.synth.distinct.n)?` (${S.find.synth.distinct.n} distinct chip plans)`:''}: <b>${v.min[1]} of them need only 1 glitch</b> instead of 3.`:'The same written design, built with other settings, often needs only 1 or 2 glitches instead of 3.'} <button class="linkb" data-go="x-chip">A whole chip design (PicoSoC)</button> · <button class="linkb" data-go="studies">All of them (Studies)</button></span></div></div>
  <p style="font-size:15px"><b>This is the core lesson, and what GlitchSAT is for:</b> a protection that is in the written design is not proof that it is in the chip. GlitchSAT checks the chip plan <i>after</i> the build tool has run, and counts how many glitches a thief really needs.</p>${Studio.fixHost?Studio.fixHost('merge'):''}`}},
 {n:'Red, blue, purple',h:'Red team, blue team, purple team',html:()=>`<p class="lead">In cybersecurity, a <b>red team</b> plays the attacker and a <b>blue team</b> defends. When both work together in a loop (attack, learn, fix, attack again) it is called a <b>purple team</b>. GlitchSAT works like a purple team for a chip design.</p>
  <div class="lz-grid3">
   <div class="lz-tile lz-how"><b style="color:var(--hot)">Red: find the cheapest break-in</b><span class="g">Think like the thief.</span><ol><li>What is the smallest number of glitches that opens the lock?</li><li>Exactly where and when must they land?</li><li>Which parts of the chip appear in the most attacks?</li></ol><span class="ex">In the app: <button class="linkb" data-go="p0">Try an attack</button>, <button class="linkb" data-go="x-spots">Weak spots</button>, <button class="linkb" data-go="x-shots">Laser shots on the chip</button>, <button class="linkb" data-go="x-lab">Clock-glitch lab</button>.</span></div>
   <div class="lz-tile lz-how"><b style="color:var(--acc)">Blue: make it harder, and keep it hard</b><span class="g">Think like the designer.</span><ol><li>Which change makes the cheapest attack more expensive?</li><li>Did the protection survive the tools that build the chip?</li><li>Can we prove a small attack never works?</li></ol><span class="ex">In the app: <button class="linkb" data-go="x-fix">Suggest a fix</button>, <button class="linkb" data-go="x-gal">Example gallery</button> (did the protection survive the build?), <button class="linkb" data-go="x-forever">Holds for any waiting time?</button>, <button class="linkb" data-go="x-rep">Evidence report</button>.</span></div>
   <div class="lz-tile lz-how"><b>Purple: the loop</b><span class="g">Attack your own design on paper, fix what you find, check the fix, repeat.</span><ol><li>Red finds: “3 copies, but the build joined them: 1 glitch is enough.”</li><li>Blue fixes: “keep the copies apart.”</li><li>Red checks again: “now 3 glitches are needed.”</li></ol><span class="ex">This loop is how the project’s own designs were studied.</span></div></div>
  <div class="lz-goals"><h3>HOW THIS DIFFERS FROM A REAL RED TEAM</h3><ol>
  <li><b>No real devices are attacked.</b> Everything happens on a model of a design, before it becomes a chip.</li>
  <li><b>It happens early.</b> A real red team tests a finished product; this finds weak spots while they are still cheap to fix.</li>
  <li><b>The goal is defence.</b> Even the attack side exists to tell the designer what to fix, and how.</li></ol></div>
  <p class="lz-note">In one line: GlitchSAT attacks your chip design on paper, so the real chip is harder to attack.</p>`},
 {n:'Who checks this',h:'Who checks this in real life?',html:()=>`<p class="lead">Chip designers harden and check their designs before the chip is made. Then independent <b>test labs</b> attack the real chips, and <b>certification schemes</b> decide whether the result is good enough for bank cards, phones or smart-home devices ${sref(14)}.</p>
  <div class="lz-grid3"><div class="lz-tile">${ic('chipi',34)}<b>Chip designers</b><span class="g">Add protections and check them early. Tools like GlitchSAT are for this stage: an early design check, not a certificate.</span></div>
  <div class="lz-tile">${ic('lock',34)}<b>Test labs</b><span class="g">Glitch real chips with voltage, clock, electromagnetic pulses and lasers, within a fixed time (for one scheme, 25 days at its Level 2 and 35 days at Level 3) ${sref(14)}.</span></div>
  <div class="lz-tile">${ic('card',34)}<b>Certification schemes</b><span class="g">Common Criteria (smartcards), EMVCo (payment chips) and PSA Certified (connected devices) score each attack in points: more time, skill and equipment means more points ${sref(14)}.</span></div></div>
  <p>Why the count matters: in PSA Certified’s own example, an attack that needs <b>two</b> glitches instead of one scores 23 points instead of 20. That moves it past what the scheme’s Level 3 asks a chip to resist, so only a Level 4 chip must withstand it ${sref(14)}. Fewer glitches needed means an easier attack, and a chip that fails a higher level.</p>
  <p class="lz-note">From the project report “GlitchSAT real world scaling”<span class="tech-only">, <span class="keep mono">reports/GlitchSAT real world scaling.md</span></span>, which quotes the scheme documents. See also the <button class="linkb" data-go="x-rep">Evidence report</button> page.</p>`},
 {n:'Check yourself',h:'Check yourself: 5 questions',html:()=>`<p class="lead">Pick an answer to see why it is right or wrong. Nothing is stored or sent anywhere; the score below is only on this screen.</p>${QS.map((q,i)=>quiz(q,i)).join('')}${score()}
  <div class="lz-tile" style="margin-top:6px"><b>Ready for the tool?</b><span class="g">You now know why the number of glitches matters. Watch a thief get in, step by step:</span><div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center"><button class="btn primary" id="lz-try">▶ Watch the first attack</button><button class="btn" data-go="found">What we found, in one minute</button><span class="lz-links">${pageLink('project','Use this in a project')} · ${pageLink('teach','Class plan (printable)')}</span></div></div>`}];
const QS=[
 {q:'Why would a thief glitch a chip instead of guessing the key?',o:[['Guessing a long key would take far longer than a lifetime; a well-timed glitch can make the check say “yes” in minutes.',1],['Because glitches are allowed by law and guessing is not.',0],['Because the key is printed on the box.',0]],
  e:'A 128-binary-digit key has about 3.4 × 10<sup>38</sup> values, so guessing is hopeless. A glitch skips the guessing altogether: in the Trezor story, about 15 minutes with the wallet in hand was enough.'},
 {q:'An engineer wrote three copies of a check. Why should someone still check the finished chip plan?',o:[['There is no need: three copies in the written design always means three glitches.',0],['The build tool may join the copies to save space, so one glitch on the shared wire could be enough again.',1],['Because copies make the chip slower.',0]],
  e:'The build tool turns the written design into the chip plan and can merge copies without warning. In this project, most ways of building the same design needed only 1 glitch. That is what GlitchSAT checks.'},
 {q:'Why is one glitch weakness in a chip model such big news?',o:[['It only affects the one device that was attacked.',0],['Every device with that chip model shares it, and a software update cannot change hardware that is already sold.',1],['Glitches wear out over time, so it fixes itself.',0]],
  e:'The ESP32 maker said there was no software fix for chips already sold, and the Trezor flaw needed a hardware redesign. One weakness can affect millions of devices at once.'},
 {q:'What is a glitch?',o:[['A mistake in the chip’s program that its maker forgot to correct.',0],['A split-second disturbance (of the power, the clock, or by light) that makes one small part of the chip give the wrong answer for one step.',1],['Trying every possible key very quickly.',0]],
  e:'A glitch is physical and brief, and it has to be timed to the moment of the check. A mistake in the program is a bug, and trying every key is guessing.'},
 {q:'A result says “3 glitches needed”. What does that mean?',o:[['The chip can be attacked only three times before it locks itself.',0],['The chip is safe: nobody can ever get in.',0],['The fewest perfectly-timed glitches that let a wrong key in is 3. With 2 or fewer, no way in was found within the limits that were searched.',1]],
  e:'It is a count for one chip plan, inside stated limits (how many glitches and how many steps were tried). More glitches needed means a harder attack. It is not a safety rating.'}];
function score(){const n=QS.length,done=QS.every((q,i)=>L.ans[i]!=null);if(!done){const k=QS.filter((q,i)=>L.ans[i]!=null).length;return k?`<p class="lz-note" style="margin:0 0 10px">${k} of ${n} answered.</p>`:''}
 const ok=QS.filter((q,i)=>L.first[i]).length;return `<div class="lz-score" role="status" id="lz-score"><span>You got <b>${ok} of ${n}</b> right on the first try.${ok===n?' Well done.':''}</span><button class="btn" id="lz-again">Try again</button></div>`}
function quiz(q,i){const a=L.ans[i];return `<div class="lz-q" role="group" aria-labelledby="lzq${i}"><h4 id="lzq${i}">${i+1}. ${q.q}</h4><div class="opts">${q.o.map((o,j)=>`<button data-q="${i}" data-o="${j}" class="${a==null?'':j===a?(o[1]?'right':'wrong'):(o[1]&&a!=null?'right':'')}" aria-pressed="${a===j}">${String.fromCharCode(65+j)}. ${o[0]}${a!=null&&j===a?(o[1]?' <b>✓ right</b>':' <b>✕ not quite</b>'):a!=null&&o[1]?' <b>✓ the right answer</b>':''}</button>`).join('')}</div>${a!=null?`<p class="ex" aria-live="polite">${q.o[a][1]?'Right. ':'Not quite. '}${q.e}</p>`:''}</div>`}
function sources(){return `<details class="lz-sources" id="lz-srcs"><summary>Sources (${LZ_SRC.length}): every true story above comes from these pages</summary><div><ol class="lz-src-list">${LZ_SRC.map((s,k)=>`<li id="lz-s${k+1}" tabindex="-1"><span class="keep">${esc(s[0])}</span>${s[1]?` · <a class="keep" href="${s[1]}" target="_blank" rel="noopener noreferrer">${esc(s[1])}</a>`:''}</li>`).join('')}</ol>
 <p class="lz-note">How to read the stories: “researchers showed” means it was demonstrated and reported, not seen used against the public; “sold” or “pirates” means it reached real users. Labelled “uncertain detail” where the sources leave a gap. Titles are given exactly as published, in both views, so they can be searched for. Links open in your browser and need the internet; the lesson itself works offline.</p></div></details>`}
function setHash(){try{const want=S.tab==='learn'?'#learn/'+(L.i+1):'';if(location.hash!==want)history.replaceState(null,'',location.pathname+location.search+want)}catch(e){}}
function draw(el){el=el||$('#v-learn');if(!el)return;const i=L.i=Math.max(0,Math.min(SCR.length-1,L.i)),s=SCR[i];L.seen[i]=1;LS.set('gs_learn_i',i);LS.set('gs_learn_seen',L.seen);setHash();
 const open=$('#lz-srcs')&&$('#lz-srcs').open;
 el.innerHTML=`<div class="lz"><nav class="lz-nav" aria-label="Lesson screens"><div class="xh">Why protect chips?</div>${SCR.map((x,j)=>`<button data-lz="${j}" class="${j===i?'on':''}${L.seen[j]?' seen':''}" aria-current="${j===i?'step':'false'}"><span class="n">${L.seen[j]&&j!==i?'✓':j+1}</span><span>${esc(x.n)}</span></button>`).join('')}</nav>
 <div class="lz-main"><div class="lz-card"><div class="lz-kick">Screen ${i+1} of ${SCR.length}<span class="lz-bar" aria-hidden="true"><i style="width:${100*(i+1)/SCR.length}%"></i></span></div><h2 id="lz-h" tabindex="-1">${esc(s.h)}</h2>${s.html()}
 <div class="lz-foot"><button class="btn" id="lz-back" ${i?'':'disabled'}>Back</button><span class="sp"></span>${i<SCR.length-1?`<span class="hint">Next: ${esc(SCR[i+1].n)}</span><button class="btn primary" id="lz-next">Next</button><span class="hint">or press →</span>`:`<button class="btn primary" id="lz-start">Back to Start</button>`}</div></div>${sources()}</div></div>`;
 if(open)$('#lz-srcs').open=true;
 el.querySelectorAll('[data-lz]').forEach(b=>b.onclick=()=>goTo(+b.dataset.lz));
 $('#lz-back').onclick=()=>goTo(i-1);if($('#lz-next'))$('#lz-next').onclick=()=>goTo(i+1);if($('#lz-start'))$('#lz-start').onclick=()=>show('start');if($('#lz-try'))$('#lz-try').onclick=()=>tryAttack();
 if($('#lz-again'))$('#lz-again').onclick=()=>{L.ans={};L.first={};draw(el);el.scrollTop=0;const h=$('#lz-h');h&&h.focus({preventScroll:true})};
 el.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{const qi=+b.dataset.q,oi=+b.dataset.o;if(L.ans[qi]==null)L.first[qi]=!!QS[qi].o[oi][1];L.ans[qi]=oi;const y=el.scrollTop;draw(el);el.scrollTop=y;const nb=el.querySelector(`[data-q="${b.dataset.q}"][data-o="${b.dataset.o}"]`);nb&&nb.focus()})}
function goTo(n,focus){L.i=n;const el=$('#v-learn');draw(el);if(el)el.scrollTop=0;if(focus!==false){const h=$('#lz-h');h&&h.focus({preventScroll:true})}}
function openLearn(n){if(S.story!=null)closeStory(true);if(S.dlg){S.dlg.opener=null;closeDlg()}if(n!=null&&!isNaN(n))L.i=n;show('learn');const h=$('#lz-h');h&&h.focus({preventScroll:true})}
/* the tab ("menu entry"): extension point */
Studio.registerView({id:'learn',title:'Why protect chips?',short:'Why protect?',after:'start',tip:'A short lesson for newcomers: what chips keep safe, true glitch-attack stories, and why protections exist',show:el=>draw(el)});
/* every lesson screen has an address (#learn/5): it survives a reload and can be put on a slide */
{const _show=window.show;window.show=function(id){_show(id);setHash()};
 const fromHash=()=>{const m=/^#learn(?:\/(\d+))?$/.exec(location.hash);if(!m)return false;LS.set('gs_seen3',1);openLearn(m[1]?Math.max(0,Math.min(SCR.length-1,+m[1]-1)):null);return true};
 addEventListener('hashchange',fromHash);setTimeout(fromHash,0)}
/* links: data-go="learn" or "learn:N" (screen N, counted from 1) */
Studio.onGo=g=>{const m=/^learn(?::(\d+))?$/.exec(g);if(!m)return false;openLearn(m[1]?(+m[1]-1):null);return true};
/* Start page link */
Studio.startExtra=()=>`<div class="lz-start">${ic('wallet',34)}${ic('game',34)}${ic('car',34)}<div><b>New to chip security?</b> Start with <button class="linkb" data-go="learn:1">Why protect chips?</button>, a lesson of about ${lzTime().m} minutes with true stories of glitch attacks on game consoles, crypto wallets and cars. <span style="color:var(--mut)">Teaching a class? ${pageLink('teach','Class plan (printable)')}</span></div></div>`;
Studio.aboutExtra=()=>`<div class="panel"><div class="ph"><h4>For teachers and student projects</h4></div><div class="pb"><p style="margin:0">${pageLink('teach','Class plan (printable)')}: a 45-minute lesson, three hands-on activities that work with saved results and nothing installed, a student sheet and the answers. ${pageLink('project','Use this in a project')}: four project ideas with a starting design each, a result table to fill in and a limitations paragraph. Every lesson screen has its own address, for example <span class="keep mono">#learn/5</span>.</p></div></div>`;
/* first-launch story: one card after "A chip has a lock" and "A thief without the key" */
if(typeof STORY!=='undefined'&&!STORY.some(c=>c.lz)){const k=STORY.findIndex(c=>c.h==='A thief without the key');
 STORY.splice(k<0?2:k+1,0,{lz:1,h:'This really happens',p:'This is not just a puzzle. Console hackers and pay-TV pirates have used this kind of trick in the real world, and researchers have shown it on <b>crypto wallets, cloud servers and car computers</b>. Curious? <button class="linkb" data-go="learn:5">Read the true stories in “Why protect chips?”</button> (a short lesson), or press <b>Next</b> to continue.',
  svg:()=>`<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="A game console, a crypto wallet and a car, each hit by a glitch">${[['game',60],['wallet',245],['car',430]].map(p=>`<g transform="translate(${p[1]},30)"><svg viewBox="0 0 52 48" width="90" height="83">${IC[p[0]]}</svg>${bolt(84,8,1.4)}</g>`).join('')}<text x="105" y="150" font-size="13" text-anchor="middle">game consoles</text><text x="290" y="150" font-size="13" text-anchor="middle">crypto wallets</text><text x="475" y="150" font-size="13" text-anchor="middle">cars</text></svg>`})}
/* a line on every Explore page: the real-world risk it relates to */
const RISK={'x-spots':['One weak part can open a whole product line, like the start-up check of every Xbox 360.',5],
 'x-fix':['A weakness found after release may need new hardware: the Trezor wallets could not be fixed by an update.',6],
 'x-forever':['A thief with a stolen wallet or a car in a garage has all the time in the world to keep trying.',6],
 'x-shots':['Test labs aim lasers at single spots of a chip; at its highest level, PSA Certified requires laser attacks to be considered.',9],
 'x-lab':['Clock glitches broke pay-TV smartcards, and the Xbox 360 hack slowed the clock to time its pulse.',5],
 'x-fw':['Glitching the start-up program let people run their own code on ESP32 gadgets, Switch consoles and Tesla car computers.',6],
 'x-hw':['A start-up check in hardware is what the AMD and Tesla attacks had to defeat.',6],
 'x-rep':['Certification schemes score attacks in points; one extra glitch can move an attack past a level.',9],
 'x-real':['These are parts of a real open-source security chip, and published research found that build tools weakened protections in such parts.',8],
 'x-chip':['Debug access on a locked device, or a start check skipped by one glitch, is what the console, AMD and Tesla attacks went after.',6],
 'x-gal':['A lock on a smart-home gadget or a boot check in a console is this small at heart; the true stories show what one glitch on such a check led to.',5]};
const lzRiskFor=id=>RISK[id]?`<p class="lz-risk"><b>Real-world risk:</b> ${RISK[id][0]} <button class="linkb" data-go="learn:${RISK[id][1]}">Why protect chips?</button></p>`:'';
function wrapExplore(v){if(v._lz)return;v._lz=1;const r=v.render;v.render=function(xc){if(xc&&xc.parentNode&&!xc.parentNode.querySelector('.lz-risk')){const d=document.createElement('div');d.innerHTML=lzRiskFor(v.id);if(d.firstChild)xc.parentNode.insertBefore(d.firstChild,xc)}return r.apply(this,arguments)}}
EXPLORE.forEach(wrapExplore);const _push=EXPLORE.push;EXPLORE.push=function(...vs){vs.forEach(wrapExplore);return _push.apply(this,vs)};
/* arrow keys move through the lesson when it is open and nothing else is */
document.addEventListener('keydown',e=>{if(S.tab!=='learn'||S.story!=null||S.dlg||S.help||e.ctrlKey||e.metaKey||e.altKey)return;const tn=e.target.tagName;if(tn==='INPUT'||tn==='SELECT'||tn==='TEXTAREA')return;
 if(e.key==='ArrowRight'&&L.i<SCR.length-1){e.preventDefault();goTo(L.i+1)}else if(e.key==='ArrowLeft'&&L.i>0){e.preventDefault();goTo(L.i-1)}});
if(S.tab==='start'&&typeof drawStart==='function')drawStart();
window.LearnView={SCR,CASES,QS,goTo,open:openLearn,sources:LZ_SRC};
})();
"""


def install(page):
    """Return the page with the lesson's style and script added (after the main script, so its helpers exist)."""
    page = page.replace('</style></head>', CSS + '</style></head>', 1)
    i = page.rfind('</body>')
    return page[:i] + '<script>' + JS + '</script>' + page[i:]


# ------------------------------------------------------------------ printable pages: /teach (class plan) and /project
# Plain HTML, no script needed to read or print them. Served by studio.py; the answer tables for the example gallery are
# filled from the saved result files at request time, so the sheet always matches what the screen shows.
PAGE_CSS = r"""
:root{--bg:#f3f5f8;--panel:#fff;--line:#cfd6df;--txt:#18212c;--mut:#4f5c6b;--acc:#1f63d8;--warn:#8a5700;--ok:#2f6b58;--inset:#f1f4f8}
html[data-theme=dark]{--bg:#0e1116;--panel:#151a21;--line:#2f3945;--txt:#e3e8ee;--mut:#9aa5b3;--acc:#6ea2ff;--warn:#e0a13a;--ok:#8fb8a8;--inset:#10141a}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Ubuntu,"Noto Sans","DejaVu Sans",sans-serif}
main{max-width:920px;margin:0 auto;padding:18px 22px 40px}
.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px}.top .sp{flex:1}
.btn{font:inherit;font-size:13.5px;background:var(--panel);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:5px 12px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
h1{font-size:26px;line-height:1.2;margin:8px 0 4px}h2{font-size:19px;margin:22px 0 6px;padding-top:10px;border-top:2px solid var(--line)}h3{font-size:15.5px;margin:14px 0 4px}
p{margin:6px 0}.sub{color:var(--mut);margin:0 0 10px}
a{color:var(--acc)}code,.mono{font-family:ui-monospace,"DejaVu Sans Mono",Menlo,Consolas,monospace;font-size:13px;background:var(--inset);border:1px solid var(--line);border-radius:4px;padding:0 4px}
table{border-collapse:collapse;width:100%;margin:6px 0 10px;background:var(--panel)}th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top;font-size:14px}
th{background:var(--inset);font-size:12.5px;letter-spacing:.3px}
td.t{white-space:nowrap;font-weight:650;width:74px}td.blank{height:30px}
.box{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:6px;padding:8px 14px;margin:8px 0}
.box.warn{border-left-color:var(--warn)}.box.ok{border-left-color:var(--ok)}
.tag{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.5px;border:1px solid var(--mut);border-radius:4px;padding:0 6px;text-transform:uppercase}
ol,ul{margin:4px 0 8px;padding-left:22px}li{margin:3px 0}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0 22px}
.sheet{break-before:page}.keep{break-inside:avoid}
.line{border-bottom:1px solid var(--mut);height:26px}
@media (max-width:760px){.cols{grid-template-columns:1fr}}
@media print{:root,html[data-theme=dark]{--bg:#fff;--panel:#fff;--line:#999;--txt:#000;--mut:#333;--acc:#000;--warn:#000;--ok:#000;--inset:#f2f2f2}
 html,body{font-size:11.5pt}main{max-width:none;padding:0}.noprint{display:none!important}a{color:#000;text-decoration:none}h2{break-after:avoid}table,.box{break-inside:avoid}@page{margin:14mm}}
"""


def _e(s):
    return str('' if s is None else s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _g(n):
    return '%d glitch%s' % (n, '' if n == 1 else 'es')


def _lab(r):
    import re
    return re.sub(r'^Run ', '', re.sub(r'^\d+\.\s*', '', r.get('label') or ''), flags=re.I)


def _gal_answer(r):
    if r.get('verdict') == 'ATTACK_FOUND':
        return _g(r['min_faults'])
    if r.get('verdict') == 'NO_ATTACK_UP_TO_BOUND':
        return 'no way in with up to %s' % _g(r.get('max_faults') or 0)
    return 'not decided'


_BUILD = {'plain': 'as written', 'synth': 'tidied across the copies', 'synth-keep': 'tidied, each copy kept as its own block', 'netlist': 'factory cells as given'}


def _gal_rows(gal, answers):
    """Rows for activity C: one per example; with answers for the teacher, blank for the student sheet."""
    out = []
    for x in (gal or {}).get('examples') or []:
        runs = sorted(x.get('runs') or [], key=lambda r: r['min_faults'] if r.get('verdict') == 'ATTACK_FOUND' else 99)
        if len(runs) < 2:
            continue
        title = (x.get('title') or x['id']).split(':')[0]
        if not answers:
            out.append('<tr><td>%s</td><td class="blank"></td><td class="blank"></td><td class="blank"></td></tr>' % _e(title))
            continue
        sv = next((r.get('survival') for r in runs if r.get('survival') and len(set(map(str, r['survival'].values()))) > 1), None)
        note = ''
        if sv:
            note = 'Survived the build? ' + '; '.join('%s: %s' % (_BUILD.get(k, k), _g(v) if isinstance(v, int) else 'no way in found') for k, v in sv.items()) + '.'
        out.append('<tr><td>%s</td><td>%s: <b>%s</b></td><td>%s: <b>%s</b></td><td>%s</td></tr>' % (
            _e(title), _e(_lab(runs[0])), _e(_gal_answer(runs[0])),
            _e(_lab(runs[-1])), _e(_gal_answer(runs[-1])), _e(note)))
    return ''.join(out)


def _shell(title, theme, body):
    th = 'dark' if theme == 'dark' else 'light'
    return ('<!doctype html><html lang="en" data-theme="%s"><head><meta charset="utf-8"><title>%s</title>'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><style>%s</style></head><body><main>'
            '<div class="top noprint"><a class="btn" href="/">← Back to GlitchSAT Studio</a><span class="sp"></span>'
            '<a class="btn" href="?theme=%s">%s page</a><button class="btn primary" onclick="window.print()">Print this page</button></div>'
            '%s</main></body></html>') % (th, _e(title), PAGE_CSS, 'light' if th == 'dark' else 'dark', 'Light' if th == 'dark' else 'Dark', body)


def _teach(ctx):
    gal = ctx.get('gallery') or {}
    has_gal = bool(gal.get('examples'))
    live = 'Results are computed live on this computer.' if ctx.get('live') else 'On this computer every number is a saved result, labelled RECORDED. Nothing is missing, and nothing has to be installed.'
    act_c = ('''<h3>Activity C · Weak against protected (the example gallery)</h3>
<p><b>Where:</b> Explore → <b>Example gallery</b>. Four small designs, each in a weak and a protected version, with saved results.</p>
<ol><li>For each design, read “What it is”. Before reading the numbers, say which version should need more glitches.</li>
<li>Write down the two numbers. For the hello lock, also copy the three lines under “Did the protection survive the build?”.</li>
<li>Write one sentence: why does the protected hello lock need fewer glitches in one of its builds than in the others? Then open <b>Why?</b> and compare.</li></ol>
<table class="keep"><tr><th>Design</th><th>Weak version</th><th>Protected version</th><th>What to notice</th></tr>%s</table>
<p><b>The sentence to look for:</b> the build that tidies across the copies joined the three checks into one, so one glitch decides again; the build that keeps each copy as its own block did not. The protection was in the written design all along, which is the “hidden danger” of lesson screen 8.</p>''' % _gal_rows(gal, True)) if has_gal else '''<h3>Activity C · Weak spots, recounted live</h3>
<p><b>Where:</b> Explore → <b>Weak spots</b>. (The example gallery is not in this project folder, so this activity replaces it.)</p>
<ol><li>Pick “Lock with three copies”. Read how many cheapest ways in there are.</li><li>Press <b>Recount every way in</b>: this runs on any computer, with nothing installed.</li>
<li>Switch to “Three copies, built so that the copies got merged” and compare the bars: which part do most ways in use now?</li></ol>'''
    sheet_c = ('<h3>C · Weak against protected (Explore → Example gallery)</h3><table><tr><th>Design</th><th>Weak version: glitches</th><th>Protected version: glitches</th><th>Why the difference?</th></tr>%s</table>' % _gal_rows(gal, False)) if has_gal else \
        '<h3>C · Weak spots (Explore → Weak spots)</h3><table><tr><th>Lock</th><th>Cheapest ways in</th><th>Glitches each</th><th>Part used most</th></tr><tr><td>Three copies</td><td class="blank"></td><td class="blank"></td><td class="blank"></td></tr><tr><td>Three copies, merged by the build</td><td class="blank"></td><td class="blank"></td><td class="blank"></td></tr></table>'
    return _shell('Class plan: glitch attacks on chips (GlitchSAT Studio)', ctx.get('theme'), '''
<h1>Class plan: can a thief glitch their way past a lock?</h1>
<p class="sub">One 45-minute lesson with GlitchSAT Studio %s · for learners aged about 16 and up · no hardware or security knowledge needed</p>
<div class="box"><b>What you need.</b> One computer with a projector (a 1280-pixel-wide picture is enough). For the hands-on part: one computer for every two students, or this page’s student sheet on paper and the projector.
<b>Nothing to install</b> beyond Python 3 and a web browser: no chip build tool, no solver, no internet. Start it with <code>python3 studio.py</code>; the lesson and every activity below are then in the window that opens. %s</div>
<div class="box warn"><b>Say this once in class.</b> Everything on screen is computed; nothing is measured on a real chip, and no chip is attacked. Each result carries a label: <span class="tag">recorded</span> saved earlier, <span class="tag">live</span> computed now,
<span class="tag">simulated</span> the physics modelled in software, <span class="tag">proved</span> for any waiting time but only for one chip plan, <span class="tag">estimate</span> a rough score. A count such as “3 glitches” holds inside stated limits and is an early design check, not a safety rating.</div>

<h2>What students can do afterwards</h2>
<ol><li>Name everyday things a chip keeps safe, and say what a thief gains by controlling it.</li><li>Say what a glitch is, and why a thief glitches a chip instead of guessing its key.</li>
<li>Explain what “3 glitches needed” means, and why three copies of a check do not always give 3.</li><li>Explain the hidden danger: the tool that builds a chip can remove a protection that is in the written design.</li></ol>

<h2>The 45 minutes</h2>
<table><tr><th>Minutes</th><th>What happens</th><th>On screen</th><th>You say or ask</th></tr>
<tr><td class="t">0 – 3</td><td><b>Hook.</b> The story of a lock, a thief and a glitch.</td><td>Button <b>How it works</b> (top right): 7 cards, press → to move.</td><td>“How would you get past a lock if you did not have the key?”</td></tr>
<tr><td class="t">3 – 13</td><td><b>Why it matters.</b> What chips guard, what a thief gains, why glitch and not guess, two true stories.</td><td>Tab <b>Why protect chips?</b>, screens <a href="/#learn/2">2</a>, <a href="/#learn/3">3</a>, <a href="/#learn/4">4</a>, then two stories from <a href="/#learn/5">5</a> and <a href="/#learn/6">6</a> (the Xbox 360 and the Trezor wallet work well). Leave “More examples” closed.</td><td>“Who did this: a researcher, or someone selling it?” (each story says). “Why can an update not repair it?”</td></tr>
<tr><td class="t">13 – 18</td><td><b>The hidden danger.</b> A build tool can join the copies.</td><td>Lesson screen <a href="/#learn/8">8</a>.</td><td>“The engineer wrote three copies. What does the chip contain?”</td></tr>
<tr><td class="t">18 – 28</td><td><b>Watch four attacks.</b> Students predict each number first.</td><td>Tab <b>Try an attack</b>; tick <b>Predict first</b>; path steps 1 to 4.</td><td>Take a show of hands for 1, 2 or 3 before each click. After step 2: “Why did the second copy not help?”</td></tr>
<tr><td class="t">28 – 40</td><td><b>Hands-on in pairs.</b> One of the three activities below.</td><td>See each activity.</td><td>Walk round; ask pairs to say their sentence aloud before they check it.</td></tr>
<tr><td class="t">40 – 45</td><td><b>Check.</b> Five questions, then one exit question on paper.</td><td>Lesson screen <a href="/#learn/11">10</a>, “Check yourself”.</td><td>“Who got all five on the first try?” (the screen shows the score).</td></tr></table>
<p class="sub">Short of time? Drop steps 3 and 4 of the path (minutes 24 to 28) and keep the hands-on part. Every lesson screen has its own address (<span class="mono">#learn/5</span>), so a screen can be linked from a slide.</p>

<h2>Three hands-on activities (no build tools needed)</h2>
<p>All three use saved results that come with the project, so they behave the same on every computer.</p>
<h3>Activity A · Predict, reveal, explain (the six-step path)</h3>
<p><b>Where:</b> tab <b>Try an attack</b>, with <b>Predict first</b> ticked. Students work through steps 1 to 6 (or 4 to 6 if you did 1 to 4 together).</p>
<ol><li>Read “What you are looking at”. Write your prediction on the sheet, then click it on screen.</li><li>Read the result sentence and “What it means”. Write one sentence in your own words: why this number?</li></ol>
<table class="keep"><tr><th>Step</th><th>Lock</th><th>Saved result</th><th>The reason to listen for</th></tr>
<tr><td>1</td><td>one check</td><td><b>1 glitch</b></td><td>One check, one deciding wire.</td></tr>
<tr><td>2</td><td>two checks</td><td><b>1 glitch</b></td><td>Both copies report into one shared wire that the designer drew; that wire decides.</td></tr>
<tr><td>3</td><td>three copies, kept apart</td><td><b>3 glitches</b></td><td>Each copy controls its own part of the answer; every copy must be fooled.</td></tr>
<tr><td>4</td><td>same design, second chip plan</td><td><b>2 glitches</b></td><td>Same written design; the build tool arranged the logic differently. The two glitches are at different steps.</td></tr>
<tr><td>5</td><td>one stored pattern changed</td><td><b>3 glitches</b></td><td>The pattern for “checking” was changed; on this chip plan that brings back 3. Not a general fix.</td></tr>
<tr><td>6</td><td>only one signal is read</td><td><b>1 glitch</b></td><td>The lock stays shut, but the rest of the chip reads one “open” signal, and that signal is faked.</td></tr></table>
<p class="sub">These are the saved results. A computer that computes live with a different version of the build tool can show another number at steps 4 and 5; the screen then says “live” and gives both.</p>

<h3>Activity B · Change one thing (saved results, side by side)</h3>
<p><b>Where:</b> tab <b>Try an attack</b> → open <b>Change the experiment yourself</b> (left) → <b>Run with these settings</b>. Then the tab <b>Compare</b> lists every attack tried, side by side.</p>
<ol><li>Choose a lock under “Which lock”. Run it once with “The whole answer” and once with “One ‘open’ signal”.</li><li>Do this for the three locks in the table. Then, for the three-copy lock, set “Chip plan” to “Made again” and run with “The whole answer”.</li>
<li>Open <b>Compare</b>. Which single change cost the most protection?</li></ol>
<table class="keep"><tr><th>Lock (first, saved chip plan)</th><th>Whole answer is read</th><th>One “open” signal is read</th></tr>
<tr><td>Lock with one check</td><td><b>1</b></td><td><b>1</b></td></tr><tr><td>Two checks, one shared wire</td><td><b>1</b></td><td><b>1</b></td></tr><tr><td>Three copies, kept apart</td><td><b>3</b></td><td><b>1</b></td></tr>
<tr><td>Three copies, chip plan made again</td><td><b>2</b></td><td>no saved result (the screen says so and offers the closest saved setting)</td></tr></table>
<p><b>The point:</b> three copies help only if the rest of the chip reads the whole answer (3 against 1), and only on a chip plan where the copies stayed apart (3 against 2). Extra: set “Glitches the thief may use” to 1 for the three-copy lock: the answer becomes “0 ways in with up to 1 glitch”. Ask what that sentence does <i>not</i> promise.</p>
%s
<div class="box ok"><b>Something that really runs, with nothing installed.</b> Explore → <b>Weak spots</b> → “Recount every way in” and “Check now”, and Explore → <b>Holds for any waiting time?</b> → “Prove again on this computer” compute on any computer in about a second and show ✓ when they match the saved numbers. A good moment to explain the difference between <i>recorded</i> and <i>live</i>.</div>

<h2>Answers to “Check yourself” (lesson screen 11)</h2>
<table class="keep"><tr><th>Question</th><th>Answer</th><th>Why</th></tr>
<tr><td>1. Why glitch a chip instead of guessing the key?</td><td><b>A</b></td><td>A 128-digit binary key has about 3.4 × 10<sup>38</sup> values; a well-timed glitch makes the check say “yes” in minutes.</td></tr>
<tr><td>2. Three copies were written. Why still check the finished chip plan?</td><td><b>B</b></td><td>The build tool may join the copies to save space; one glitch on the shared wire is then enough.</td></tr>
<tr><td>3. Why is one weakness in a chip model big news?</td><td><b>B</b></td><td>Every device with that chip shares it, and an update cannot change hardware already sold.</td></tr>
<tr><td>4. What is a glitch?</td><td><b>B</b></td><td>A split-second disturbance of power, clock or light that makes one small part answer wrongly for one step.</td></tr>
<tr><td>5. What does “3 glitches needed” mean?</td><td><b>C</b></td><td>The fewest perfectly-timed glitches that get in is 3; with 2 or fewer none was found, within the limits searched.</td></tr></table>
<p><b>Exit question (on paper, one sentence):</b> “An engineer says: my design has three copies of the check, so it needs three glitches. What would you ask?” <i>Listen for:</i> Are the copies still separate in the chip plan after the build tool ran? Does the rest of the chip read the whole answer or one signal?</p>

<h2>Five questions for discussion</h2>
<ol><li>The Xbox 360 glitch worked about one start in four. Why is that still enough for an attacker?</li><li>Researchers publish how they broke a chip. Is that helpful or harmful, and for whom?</li>
<li>A maker says a weakness “cannot be fixed by an update”. What can owners do, and what should the maker do next time?</li><li>The tool reports “no way in with up to 3 glitches within 6 steps”. Is the chip safe? What would you want to know next?</li>
<li>Why might a company ship a chip without checking what the build tool did to its protections? What would make checking easier?</li></ol>

<h2>What these numbers do and do not say</h2>
<ul><li>They come from a computer model in which a glitch makes one wire or memory cell give the wrong answer for one step. Real glitches can behave differently.</li>
<li>Each count belongs to one chip plan and holds inside stated limits (how many glitches, how many steps). “None found” is not “safe”.</li>
<li>The example locks are toy designs with fewer than 100 gates. The true stories in the lesson are reported events with their sources listed on screen; they are not results of this app.</li></ul>

<div class="sheet"><h1>Student sheet: glitch attacks on chips</h1><p class="sub">Name: ______________________ &nbsp; Date: ____________ &nbsp; Everything on screen is computed; no real chip is attacked.</p>
<h3>A · Predict, reveal, explain (tab “Try an attack”, with “Predict first” ticked)</h3>
<table><tr><th>Step</th><th>Lock</th><th>My prediction</th><th>Result</th><th>Why? (one sentence)</th></tr>%s</table>
<h3>B · Change one thing (“Change the experiment yourself”, then the tab “Compare”)</h3>
<table><tr><th>Lock</th><th>Whole answer is read</th><th>One “open” signal is read</th></tr><tr><td>Lock with one check</td><td class="blank"></td><td class="blank"></td></tr><tr><td>Two checks, one shared wire</td><td class="blank"></td><td class="blank"></td></tr><tr><td>Three copies, kept apart</td><td class="blank"></td><td class="blank"></td></tr><tr><td>Three copies, chip plan made again</td><td class="blank"></td><td>(no saved result)</td></tr></table>
<p>Which single change cost the most protection?</p><div class="line"></div>
%s
<h3>Exit question</h3><p>An engineer says: “My design has three copies of the check, so it needs three glitches.” What would you ask?</p><div class="line"></div><div class="line"></div></div>
''' % (_e(ctx.get('version') or ''), _e(live), act_c,
       ''.join('<tr><td>%d</td><td>%s</td><td class="blank"></td><td class="blank"></td><td class="blank"></td></tr>' % (i + 1, n) for i, n in enumerate(
           ['one check', 'two checks', 'three copies, kept apart', 'same design, second chip plan', 'one stored pattern changed', 'only one signal is read'])), sheet_c))


def _project(ctx):
    gal = ctx.get('gallery') or {}
    hello = next((x for x in gal.get('examples') or [] if x['id'] == 'hello_lock'), None)
    sv = next((r.get('survival') for r in (hello or {}).get('runs') or [] if r.get('survival') and 'synth-keep' in r['survival']), None)
    seen = ''
    if sv:
        seen = '<p class="sub">Saved result for the protected hello lock, as a starting row: ' + '; '.join(
            '%s: %s' % (_BUILD.get(k, k), _g(v) if isinstance(v, int) else 'no way in found within the limits') for k, v in sv.items()) + '.</p>'
    return _shell('Use GlitchSAT in a project', ctx.get('theme'), '''
<h1>Use this in a project</h1>
<p class="sub">For students who know some digital design (Verilog, synthesis) and want a small, honest project on fault attacks. GlitchSAT %s.</p>
<div class="box"><b>Two tools, one name.</b> The Studio’s path, Explore pages and Studies come from the built-in engine (<span class="mono">scripts/glitchsat.py</span>, solver z3; options <span class="mono">--k</span> and <span class="mono">--cycles</span>).
“Open my design” and the example gallery use the own-design tool (<span class="mono">glitchsat run</span> with a project file; there the same two limits are called <span class="mono">max_faults</span> and <span class="mono">horizon</span>). Say in your report which one produced each number.</div>
<div class="box warn"><b>What you need.</b> Reading saved results needs nothing. Analysing a design of your own needs the build tool Yosys (0.33 or newer); the Studio’s live path also needs the solver z3. A first check: <span class="mono">yosys -V</span> and <span class="mono">python3 -c "import z3"</span>.
Own designs get the synthesis question only (does the protection survive the build?). The laser-spot analysis exists for the built-in layouts only.</div>

<h2>Four project ideas, each with a starting design</h2>
<table><tr><th>Idea</th><th>Start from</th><th>What you vary</th><th>What a result looks like</th></tr>
<tr><td><b>1. Does redundancy survive synthesis?</b></td><td>The hello lock of the example gallery (weak and protected version).</td><td>The synthesis flow: structure-preserving, flattened and optimised, optimised with each copy kept as its own module.</td><td>One row per flow: fewest faults, and whether the three copies are still present in the netlist.</td></tr>
<tr><td><b>2. Harden a state machine.</b></td><td>The three-copy lock of the path (steps 3 to 5), or a small FSM of your own.</td><td>The state encoding (binary, one-hot, sparse, with a distance of at least one more than the faults to resist) and whether the tool may re-encode it.</td><td>Fewest faults before and after, per encoding, on the same flow; the Studio’s “Suggest a fix” page shows the pattern.</td></tr>
<tr><td><b>3. An industrial primitive against a plain one.</b></td><td>The OpenTitan counter of the example gallery, next to a plain counter.</td><td>The primitive (plain, duplicated, cross-counted) and the property (“the count changes and no error is raised”).</td><td>Fewest faults per version, where the faults land, and whether the answer also holds for any number of cycles.</td></tr>
<tr><td><b>4. Placement spacing.</b></td><td>The built-in layouts on “Laser shots on the chip”.</td><td>How far apart the copies are placed; the spot radius.</td><td>The smallest spot radius at which one shot is enough, per layout. Note that further apart was not always better in the saved results, and say that you did not establish why.</td></tr></table>
%s
<h2>How would you fix it? The four remedies to try</h2>
<ol><li><b>Keep the copies.</b> One module per copy with <span class="mono">(* keep_hierarchy *)</span>, or synthesise without flattening and flatten afterwards; <span class="mono">(* keep *)</span> on the copies’ outputs. Commercial flows: <span class="mono">set_dont_touch</span>.</li>
<li><b>Choose the encoding.</b> Sparse state codes written by hand; switch FSM re-encoding off (<span class="mono">synth -nofsm</span> or <span class="mono">(* fsm_encoding = "none" *)</span>). Measure the distance in the netlist.</li>
<li><b>Place the copies apart.</b> One placement region per copy, other logic in between; carry the dont_touch through placement.</li>
<li><b>Barriers.</b> A hand-instantiated, size-only buffer or flip-flop between each copy and the combine point; in C, volatile reads or a value passed through an empty asm statement.</li></ol>
<p>After every change, analyse the final netlist again. A remedy in the RTL is not evidence. The Studio shows the same list under “How would you fix it?” on its result pages, with what was seen in the saved results.</p>

<h2>A result table to fill in</h2>
<table><tr><th>Design and version</th><th>Flow (tool and version)</th><th>Property (“must never happen”)</th><th>Limits (max faults, cycles)</th><th>Fewest faults</th><th>Where they land</th><th>Any number of cycles?</th><th>Copies still present?</th></tr>
<tr><td class="blank"></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td class="blank"></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td class="blank"></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table>
<p class="sub">Also record: the netlist’s sha256, the tool versions, the attacker’s inputs, the reset and power-up assumptions, and the run time. A number without these cannot be reproduced.</p>

<h2>A limitations paragraph you can adapt</h2>
<div class="box"><p>“The fault counts in this report come from a formal model, not from measurements on hardware. A fault is modelled as the inversion of one gate output or flip-flop output for one clock cycle; multi-bit, timing and analogue effects are not modelled. Each count is the smallest number of such faults that violates the stated property on one specific netlist, within a bound of <i>k</i> faults and <i>N</i> clock cycles after a normal reset; where an unbounded proof is reported, it removes the cycle bound only. The counts depend on the synthesis flow and tool version, and say nothing about another netlist of the same RTL. Placement is not considered unless stated. The designs are small examples. The results are an early design check and not a security evaluation of a product.”</p></div>
<p class="sub">Related, already published: solver-based fault analysis is an established field, and the SYNFI study showed earlier that synthesis can remove redundancy. Cite such work; do not present the effect as new.</p>
''' % (_e(ctx.get('version') or ''), seen))


def page(kind, ctx):
    """HTML of a printable page: 'teach' (class plan and student sheet) or 'project'."""
    return _project(ctx) if kind == 'project' else _teach(ctx)
