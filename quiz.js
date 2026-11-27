const $ = id => document.getElementById(id);
const games = {sts1:'Slay the Spire 1', sts2:'Slay the Spire 2'};
const letters = 'ABCDEFGHI';
const saveKey = 'spire-trivia:text200-v7:1';
const bank = {sts1:[], sts2:[]};
const emptyGame = () => ({index:0, answers:{}});
const progress = {game:'sts1', sts1:emptyGame(), sts2:emptyGame()};
let answerPage = 0;
let pageSize = 8;
let resultsOpen = false;

const active = () => progress[progress.game];
const questions = () => bank[progress.game];
const current = () => questions()[active().index];

function loadProgress() {
  try {
    const saved = JSON.parse(localStorage.getItem(saveKey));
    if (!saved) return;
    if (Object.hasOwn(games,saved.game)) progress.game = saved.game;
    for (const game of Object.keys(games)) {
      const stored = saved[game];
      if (!stored || !Number.isInteger(stored.index)) continue;
      progress[game].index = Math.max(0, Math.min(stored.index,bank[game].length-1));
      for (const q of bank[game]) {
        const letter = stored.answers?.[q.id];
        if (typeof letter === 'string' && /^[A-I]$/.test(letter)) progress[game].answers[q.id] = letter;
      }
    }
  } catch { /* The quiz can be played without browser storage. */ }
}
function save() { try { localStorage.setItem(saveKey,JSON.stringify(progress)); } catch {} }
function totals() {
  const stats = {correct:0,wrong:0,passed:0};
  for (const q of questions()) {
    const letter = active().answers[q.id];
    if (letter) stats[letter === q.answer ? 'correct' : letter === 'I' ? 'passed' : 'wrong']++;
  }
  return {...stats,score:stats.correct-stats.wrong,answered:stats.correct+stats.wrong+stats.passed};
}
function points(value) { return value + (Math.abs(value) === 1 ? ' point' : ' points'); }

function makeChoice(q,index) {
  const button = document.createElement('button');
  const key = letters[index];
  const chosen = active().answers[q.id];
  button.type = 'button';
  button.className = 'option';
  button.dataset.letter = key;
  button.setAttribute('aria-keyshortcuts',key);
  const marker = document.createElement('span');
  marker.className = 'letter';
  marker.setAttribute('aria-hidden','true');
  marker.textContent = key;
  const copy = document.createElement('span');
  copy.textContent = q.choices[index];
  button.append(marker,copy);
  button.setAttribute('aria-label',key + '. ' + q.choices[index] +
    (chosen && key === q.answer ? ' (correct answer)' : chosen === key ? ' (your answer)' : ''));
  if (chosen) {
    button.disabled = true;
    if (key === q.answer) button.classList.add('correct');
    else if (key === chosen) button.classList.add('wrong');
  }
  return button;
}

function drawOptions(start,size) {
  const q = current();
  $('choices').replaceChildren(...q.choices.slice(start,Math.min(start+size,8)).map((_,i)=>makeChoice(q,start+i)));
}
function drawAnswerPage() {
  const max = Math.ceil(8/pageSize)-1;
  answerPage = Math.max(0,Math.min(answerPage,max));
  drawOptions(answerPage*pageSize,pageSize);
  $('choice-pager').hidden = max === 0;
  $('choice-range').textContent = 'Options ' + letters[answerPage*pageSize] +
    (pageSize > 1 ? '–' + letters[Math.min((answerPage+1)*pageSize,8)-1] : '');
  $('earlier').disabled = answerPage === 0;
  $('later').disabled = answerPage === max;
}
function fitAnswers() {
  if (resultsOpen || !current()) return;
  // Some questions have eight full card descriptions. Page the options only
  // when the longest page would overflow the available screen at this size.
  const start = answerPage*pageSize;
  for (const size of [8,4,2,1]) {
    $('choice-pager').hidden = size === 8;
    let fits = true;
    for (let n=0;n<8;n+=size) {
      drawOptions(n,size);
      if ($('choices').getBoundingClientRect().height > $('answers-area').clientHeight + 0.5) {
        fits = false; break;
      }
    }
    if (fits || size === 1) { pageSize = size; break; }
  }
  answerPage = Math.floor(start/pageSize);
  drawAnswerPage();
}

function render() {
  const q = current();
  const stats = totals();
  const total = questions().length;
  const chosen = active().answers[q.id];
  for (const b of document.querySelectorAll('[data-game]')) b.setAttribute('aria-pressed',String(b.dataset.game===progress.game));
  $('score').textContent = points(stats.score);
  $('quiz').hidden = resultsOpen;
  $('results').hidden = !resultsOpen;
  $('prev').disabled = !resultsOpen && active().index === 0;
  $('next').disabled = resultsOpen;
  const atEnd = active().index === total-1;
  $('next').setAttribute('aria-label',atEnd ? 'See results' : 'Next question');
  $('next').title = atEnd ? 'See results' : 'Next question';
  $('position').textContent = resultsOpen ? stats.answered + ' of ' + total + ' answered' : 'Question ' + (active().index+1) + ' of ' + total;
  $('bar').style.width = 100*(resultsOpen ? stats.answered : active().index+1)/total+'%';
  if (resultsOpen) {
    $('result-game').textContent = games[progress.game];
    $('result-title').textContent = stats.answered === total ? 'Quiz complete' : 'Your results so far';
    $('result-points').textContent = points(stats.score);
    const fields = [['Correct',stats.correct],['Wrong',stats.wrong],['Passed',stats.passed]];
    $('breakdown').replaceChildren(...fields.map(([name,value])=>{
      const block=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');
      dt.textContent=name;dd.textContent=value;block.append(dt,dd);return block;
    }));
    $('resume').textContent = stats.answered === total ? 'Play again' : 'Continue quiz';
    $('review').disabled = stats.answered === 0;
    return;
  }
  $('category').textContent = q.category[0].toUpperCase()+q.category.slice(1);
  $('version').textContent = progress.game === 'sts2' ? 'v0.107.1' : 'Original game';
  const [title,...details] = q.prompt.split('\n');
  $('question').textContent = title;
  $('context').textContent = details.join('\n').trim();
  $('pass').disabled = Boolean(chosen);
  $('pass').classList.toggle('passed', chosen === 'I');
  $('choices').classList.toggle('short-options',q.choices.slice(0,8).every(text=>text.length<=22));
  $('feedback').classList.toggle('scoring',!chosen);
  $('feedback').textContent = !chosen ? 'Correct +1 · Wrong −1 · Pass 0' : chosen===q.answer ? 'Correct · +1 point' :
    chosen==='I' ? 'Passed · Answer ' + q.answer + ' · 0 points' : 'Answer ' + q.answer + ' · −1 point';
  fitAnswers();
}
function navigate(index) {
  if(!current()) return;
  const length=questions().length;
  resultsOpen=index>=length;
  active().index=Math.max(0,Math.min(index,length-1));
  answerPage=0;save();render();$(resultsOpen?'result-title':'question').focus({preventScroll:true});
}
function answer(letter) {
  if (!current() || resultsOpen || active().answers[current().id]) return;
  active().answers[current().id]=letter;save();render();
  answerPage=Math.floor(letters.indexOf(current().answer)/pageSize);drawAnswerPage();
  $('next').focus({preventScroll:true});
}
$('choices').addEventListener('click',e=>{const b=e.target.closest('button[data-letter]');if(b)answer(b.dataset.letter);});
$('pass').addEventListener('click',()=>answer('I'));
$('prev').addEventListener('click',()=>navigate(resultsOpen?questions().length-1:active().index-1));
$('next').addEventListener('click',()=>navigate(active().index+1));
$('earlier').addEventListener('click',()=>{answerPage--;drawAnswerPage();});
$('later').addEventListener('click',()=>{answerPage++;drawAnswerPage();});
$('resume').addEventListener('click',()=>{
  const first=questions().findIndex(q=>!active().answers[q.id]);
  if (first<0) progress[progress.game]=emptyGame();
  navigate(Math.max(0,first));
});
$('review').addEventListener('click',()=>navigate(questions().findIndex(q=>active().answers[q.id])));
for (const b of document.querySelectorAll('[data-game]')) b.addEventListener('click',()=>{
  if(!current() || progress.game===b.dataset.game) return;
  progress.game=b.dataset.game;resultsOpen=false;answerPage=0;save();render();
});
document.addEventListener('keydown',e=>{
  if (e.repeat||e.ctrlKey||e.metaKey||e.altKey||!current()) return;
  if (/^[a-i]$/i.test(e.key) && !resultsOpen){e.preventDefault();answer(e.key.toUpperCase());}
  if (e.key==='ArrowRight' && !resultsOpen){e.preventDefault();$('next').click();}
  if (e.key==='ArrowLeft'){e.preventDefault();$('prev').click();}
});
let resizeFrame;
function queueFit(){cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(fitAnswers);}
window.addEventListener('resize',queueFit);
window.visualViewport?.addEventListener('resize',queueFit);

// Move the painted strips closest to the mouse a little farther than the rest.
const mural = document.querySelector('.mural');
const strips = Array.from(mural.children);
const muralMotion = matchMedia('(any-hover: hover) and (any-pointer: fine) and (prefers-reduced-motion: no-preference)');
let pointerFrame = 0;
let pointerX = 0;
let pointerY = 0;

function paintMural() {
  pointerFrame = 0;
  mural.style.translate = '0 ' + ((pointerY - 0.5) * 14) + 'px';
  strips.forEach((strip, index) => {
    const distance = Math.abs(pointerY - (index + 0.5) / strips.length);
    const reach = 7 + 19 * Math.max(0, 1 - 2 * distance);
    strip.style.transform = 'translateX(' + (pointerX * reach) + 'px)';
  });
}
function followPointer(event) {
  if (event.pointerType === 'touch') return;
  pointerX = 2 * event.clientX / innerWidth - 1;
  pointerY = event.clientY / innerHeight;
  if (!pointerFrame) pointerFrame = requestAnimationFrame(paintMural);
}
function settleMural() {
  cancelAnimationFrame(pointerFrame);
  pointerFrame = 0;
  mural.style.removeProperty('translate');
  strips.forEach(strip => strip.style.removeProperty('transform'));
}
function configureMuralMotion() {
  if (muralMotion.matches) {
    window.addEventListener('pointermove', followPointer, {passive:true});
  } else {
    window.removeEventListener('pointermove', followPointer);
    settleMural();
  }
}
document.documentElement.addEventListener('pointerleave', settleMural);
window.addEventListener('blur', settleMural);
muralMotion.addEventListener('change', configureMuralMotion);
configureMuralMotion();

try {
  const response=await fetch('./data/questions.json');
  if (!response.ok) throw Error('Question bank unavailable');
  const data=await response.json();
  for (const q of data.questions) bank[q.game].push(q);
  loadProgress();render();document.fonts.ready.then(queueFit);
} catch {
  $('question').textContent='Couldn’t load the question bank.';
  $('context').textContent='Refresh to try again, or open the question bank on GitHub.';
  for(const b of document.querySelectorAll('button')) b.disabled=true;
}
