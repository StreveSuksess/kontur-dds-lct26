import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';

// Separate current deck. This generator never writes earlier presentations.
const ROOT=process.cwd();
const SKILL=process.env.PRESENTATION_SKILL_DIR||path.join(os.homedir(),'.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations');
const RUNTIME=process.env.PRESENTATION_RUNTIME_DIR||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const BUILD=path.join(ROOT,'runtime/presentation-v3-build');
const OUT=path.join(ROOT,'deliverables');
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const FONT=resolvePresentationFont({fontFamily:'Arial'});
const COLORS={ink:'#203538',accent:'#3D6E61',paper:'#F7F9F6',muted:'#61736D',line:'#D7E0D8',white:'#FFFFFF',light:'#BED3C4'};
const qa='https://drive.google.com/file/d/1qpYkmGuSVKPBrBQgC_WB5luTcDzr0ZW9/view';
const load=JSON.parse(await fs.readFile(path.join(ROOT,'docs/load-test-results.json'),'utf8'));
const bench=JSON.parse(await fs.readFile(path.join(ROOT,'docs/benchmark-results.json'),'utf8'));
const model=await fs.readFile(path.join(ROOT,'docs/model-comparison.md'),'utf8');
if(!model.includes('32/48')||!model.includes('четыре')&&!model.includes('4B'))throw new Error('Model comparison has changed; review the model slide');
if(bench.assertions_total!==48||bench.assertions_supported!==28||bench.exact_matches!==27)throw new Error('Benchmark changed; review the evidence slide');
await fs.mkdir(BUILD,{recursive:true});await fs.mkdir(OUT,{recursive:true});
const presentation=Presentation.create({slideSize:{width:1280,height:720}});
let serial=0;
function text(slide,value,x,y,w,h,size=27,color=COLORS.ink,bold=false){
  const box=slide.shapes.add({geometry:'textbox',name:`text-${++serial}`,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  box.text=value;box.text.style={typeface:FONT,fontSize:size,bold,color,autoFit:'none',insets:{left:0,right:0,top:0,bottom:0},verticalAlignment:'top'};return box;
}
function slide(title,notes='',dark=false){
  const item=presentation.slides.add();item.background.fill=dark?COLORS.ink:COLORS.paper;
  if(title)text(item,title,64,50,1152,94,46,dark?COLORS.white:COLORS.ink,true);
  text(item,String(presentation.slides.items.length).padStart(2,'0'),1170,665,48,25,18,dark?COLORS.light:COLORS.muted);
  item.speakerNotes.textFrame.setText(notes);return item;
}
function caption(item,value,dark=false){text(item,value,64,625,1110,48,20,dark?COLORS.light:COLORS.muted);}
function rows(item,items,{y=175,step=94,labelX=64,labelW=365,bodyX=465,bodyW=745,labelSize=29,bodySize=26}={}){
  items.forEach((entry,index)=>{const top=y+index*step;text(item,entry[0],labelX,top,labelW,76,labelSize,COLORS.ink,true);text(item,entry[1],bodyX,top,bodyW,80,bodySize,COLORS.muted);});
}
function table(item,values,{x=64,y=168,w=1152,h=360,widths=[330,380,442],fontSize=24}={}){
  const result=item.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
  result.borders.assign({style:'solid',fill:COLORS.line,width:1});
  for(let row=0;row<values.length;row++){
    result.rows[row].height=h/values.length;
    for(let col=0;col<values[0].length;col++){
      const cell=result.getCell(row,col);cell.fill=row===0?COLORS.ink:COLORS.white;
      cell.text.style={typeface:FONT,fontSize,bold:row===0,color:row===0?COLORS.white:COLORS.ink,autoFit:'none',verticalAlignment:'middle',insets:{left:14,right:14,top:10,bottom:10}};
    }
  }
  return result;
}
async function shot(item,file,alt,x=64,y=164,w=842,h=445){
  const source=path.join(OUT,'assets',file);const bytes=await fs.readFile(source);
  item.images.add({blob:new Uint8Array(bytes),contentType:'image/png',alt,fit:'contain',position:{left:x,top:y,width:w,height:h}});
}

// 1: Scope on the cover, with no implied production deployment.
{
  const s=slide('',`Источники: docs/product-research.md, docs/coverage.md, docs/benchmark-results.json; Q&A ${qa}. Текущий прототип включает ДДС и ограниченный текстовый путь 112. Инженерная и педагогическая проверка имеют разные статусы.`,true);
  text(s,'Контур ДДС',64,184,1140,120,84,COLORS.white,true);
  text(s,'Учебные действия ДДС\nи текстовый путь 112',68,330,1080,132,40,COLORS.light);
  text(s,'Демонстрация прототипа и проверяемого разбора',68,557,1110,50,25,COLORS.white);
}
// 2: Two written roles, with the new limited 112 exercise described honestly.
{
  const s=slide('Два учебных пути в письменном ТЗ',`docs/product-research.md; docs/coverage.md; backend/app/routes/intake112.py. Q&A ${qa}, 17:42–18:51, 21:41–24:11: приоритет первого MVP — работа ДДС с готовой карточкой. Поздние ответы в чате №624–625 и №642 подтверждают, что общий объём ТЗ включает первичный 112. Малое упражнение 112 текстовое, на двух синтетических вводных. Входящий голосовой диалог и передача карточки в ДДС отсутствуют.`);
  rows(s,[['ДДС','Готовая карточка, статусы, учебный звонок, разбор'],['112','Текстовая вводная, заполнение полей и выбор служб'],['Ограничение 112','Два синтетических случая, без входящего голоса и передачи карточки']],{y:180,step:120,labelW:320,bodyX:390,bodyW:800,bodySize:27});
  caption(s,'Путь 112 покрыт частично. Приоритет ДДС не отменяет вторую роль из письменного ТЗ.');
}
// 3: The two exercise clocks and first meaningful status.
{
  const s=slide('Первые действия и время',`Основание: ответ заказчика в чате №781; docs/coverage.md; backend/app/assessment.py; backend/tests/test_assessment.py. Время отсчитывается от начала учебной попытки. 30 секунд — открыть карточку. 3 минуты — впервые сохранить статус с непустым текстовым комментарием, независимо от завершения попытки. Параметры упражнения настраивает преподаватель. Это учебные пороги, не внешний норматив.`);
  rows(s,[['30 секунд','Открыть карточку после поступления'],['3 минуты','Впервые сохранить статус с текстом'],['«В работе»','Рабочее состояние карточки видно в интерфейсе'],['Завершение','Отдельный этап; трёхминутный порог его не заменяет']],{y:166,step:105,labelW:320,bodyX:390,bodyW:800,bodySize:27});
  caption(s,'Два учебных порога. Наличие текста без сохранённого статуса не выполняет второй.');
}
// 4: Authentic prototype screen, explicitly labeled.
{
  const s=slide('Рабочее место диспетчера',`Фактический экран RC1 из deliverables/assets/workspace-viewport.png. Дизайн учебного АРМ основан на скриншотах, предоставленных заказчиком, и Q&A 25:15–27:47. Методист не проверял применимость к действующему рабочему АРМ. Программный учебный телефон без реальной SIP-сети.`);
  await shot(s,'workspace-viewport.png','Фактический экран АРМ обучающегося');
  text(s,'Готовая карточка',945,180,274,85,28,COLORS.ink,true);text(s,'Поля и статусы по\nскриншотам заказчика.\nМетодист ещё не проверял.',945,265,274,120,23,COLORS.muted);
  text(s,'Учебный доклад',945,401,274,70,28,COLORS.ink,true);text(s,'Номер контакта, реплика и ответ сохраняются в журнале',945,480,274,116,25,COLORS.muted);
  caption(s,'Снимок раннего прототипа. Учебные данные. Применимость к рабочему АРМ не проверена.');
}
// 5: Concurrent teacher delivery and learner queue, verified by focused checks.
{
  const s=slide('Очередь одновременно поступивших карточек',`Источник: backend/app/routes/sessions.py, frontend/src/pages/Sessions.tsx, frontend/src/pages/Workspace.tsx, backend/tests/test_arrival_queue.py. Преподаватель выбирает заранее назначенные карточки и доставляет их одной операцией. Сервер атомарно переводит каждую из assigned в active с общим started_at. Ученик видит все активные карточки и переключается между ними; у каждой отсчёт идёт с поступления. Проверка: 24 focused backend/workflow tests и frontend production build. Ограничение запроса: до 100 ID. Ограничений одна в минуту или максимум три карточки нет.`);
  rows(s,[['Преподаватель','Выбирает назначенные карточки и доставляет вместе'],['Сервер','Общий момент поступления; каждая карточка активна'],['Ученик','Видит очередь и переключается между карточками'],['Таймеры','Идут от поступления каждой карточки']],{y:164,step:105,labelW:300,bodyX:385,bodyW:810,bodySize:26});
  caption(s,'Проверено тестами и сборкой. Живой класс с несколькими карточками ещё не исследован.');
}
// 5: RC2 contribution, native editable evidence table.
{
  const s=slide('Покритериальное решение преподавателя',`Контракт RC2: docs/specs/criterion-review.md, docs/api-contract.md; реализация backend/app/expert_review.py и frontend/src/components/CriterionReview.tsx. Таблица описывает механизм, не является скриншотом исследования с пользователем. Исходная оценка правил неизменна; решение по критерию и обоснование сохраняются отдельно; общий итог подтверждается явно.`);
  table(s,[['Этап','Что остаётся в отчёте','Что видит преподаватель'],['Исходный вывод','Статус, балл, события и версия','Автоматическое основание замечания'],['Решение по критерию','Отдельный исход и причина','Выполнено, не выполнено или проверить'],['Общий итог','Подтверждённый балл с ревизией','После новой правки нужен повторный разбор']],{h:368,widths:[280,390,482],fontSize:24});
  text(s,'Учитель разрешает спорный факт без потери исходного вывода',64,558,1150,54,30,COLORS.accent,true);
  caption(s,'Код RC2 есть; экономия времени и удобство для преподавателей ещё не измерены.');
}
// 6: Local architecture and AI responsibility.
{
  const s=slide('Локальная работа и границы AI',`Источники: docs/architecture.md, docs/local-ai.md, docs/local-ai-validation.json, docs/ui-validation.md. Qwen3-1.7B выполняет узкую генерацию и экспериментальные подсказки, не выставляет итоговую оценку. Whisper-small возвращает черновик распознанного текста; учащийся подтверждает его перед отправкой. Linux и целевой i5/16 ГБ не проверены.`);
  table(s,[['Компонент','Учебная функция','Кто подтверждает результат'],['React + FastAPI','Карточка, журнал и разбор','Преподаватель'],['Whisper small','Черновик доклада из записи','Учащийся перед отправкой'],['Qwen3-1.7B','Черновик сценария, узкий совет','Преподаватель проверяет факты']],{h:354});
  text(s,'Баллы задают правила и решение преподавателя',64,557,1152,52,31,COLORS.accent,true);
  caption(s,'Полный текстовый цикл работает локально без моделей. Голосовые сервисы опциональны.');
}
// 7: Model research gate, no automatic score claim.
{
  const s=slide('Модель 4B не прошла заданный порог',`Источник: docs/model-comparison.md и docs/model-comparison.json. До запросов зафиксированы 24 минимальные пары, 48 авторских синтетических примеров и пороги: 44/48 точных, улучшение ≥5, ноль ложных подтверждений, p95 ≤15с, RSS ≤8ГиБ. Qwen3-4B: 32/48, +10 к 1.7B, 4 ложных подтверждения, p95 7.28с, RSS5.40ГиБ; gate не пройден. Набор не проверен методистами и не является реальной точностью.`);
  table(s,[['На 48 синтетических случаях','Qwen3-1.7B','Qwen3-4B'],['Верный ответ и допустимая схема','22 / 48','32 / 48'],['Ложное подтверждение критерия','11','4'],['Допустимая схема ответа','48 / 48','39 / 48'],['Время ответа p95','3,22 с','7,28 с']],{h:368,widths:[560,296,296],fontSize:25});
  text(s,'Требовались 44/48 и ноль ложных подтверждений',64,558,1150,52,30,COLORS.accent,true);
  caption(s,'Простая замена модели не решает проверку адресов, ролей и причинной последовательности.');
}
// 8: RC1 engineering evidence. Never relabel as a human pilot.
{
  const s=slide('Покрытие и инженерные замеры',`Источники: docs/load-test-results.json generated_at=${load.generated_at}; docs/benchmark-results.json generated_at=${bench.generated_at}; docs/evaluation-report.md. Короткий HTTP API burst на Mac arm64/48ГБ, 1 worker SQLiteWAL. Авторский синтетический набор: 48 утверждений, 28 поддержаны, 27 из них точно совпали, 20 не поддержаны. Это не процент точности на всех 48 и не реальная точность. Нет независимой методистской разметки и реальных попыток. Не измерялись живой класс, длительная нагрузка, перенос навыка.`);
  table(s,[['Проверка','Измерение','Граница вывода'],['API: 100 пользователей',`p95 ${Math.round(load.read_100_users.p95_ms)} мс; ${load.read_100_users.errors} ошибок`,'Короткая серия запросов RC1'],['20 активных попыток',`${load.persistence.stored_status_events}/${load.persistence.expected_status_events} событий`,'Все события прогона RC1'],['Синтетический набор',`${bench.assertions_supported}/48 покрыты; ${bench.exact_matches}/28 точно`,'20 случаев без результата']],{h:352,widths:[390,330,432]});
  text(s,'Реальные учебные данные и методистский эталон ещё нужны',64,558,1150,54,29,COLORS.accent,true);
  caption(s,'API-замер RC1 не подтверждает нагрузку изменённой версии или учебный эффект.');
}
// 9: Pre-registered human study remains a plan.
{
  const s=slide('Методистский пилот: протокол готов',`Источник: docs/pilot-protocol.md и docs/pilot-templates/README.md. План: 2 преподавателя, 6–8 учащихся, 45–60 минут; независимый разбор обезличенных журналов и сопоставимые задания. В обоих условиях, ручном и продуктовом, планируется симметрично измерять подготовку, проверку, исправления и обратную связь. До исследования нужно зафиксировать сценарии, критические критерии и процедуры. Формы пусты, людей не тестировали.`);
  rows(s,[['Преподаватели','Два человека проверяют случаи вручную и в продукте'],['Учащиеся','6–8 человек выполняют исходное и новое задание'],['Эталон','Раздельные экспертные решения по каждому критерию'],['Время','В обоих условиях замерим подготовку, проверку и исправления']],{y:169,step:101,labelW:360,bodyX:480,bodyW:730,bodySize:26});
  caption(s,'Исследование ещё не проводилось. Порог экономии 20% задан заранее как гипотеза.');
}
// 10: Concrete next research decision, not an achieved outcome.
{
  const s=slide('Следующий этап: учебный пилот',`docs/pilot-protocol.md, разделы 8–10: ≥20% медианной экономии активного времени у каждого из двух преподавателей при корректной проверке — заранее заданный ориентир; не наблюдённый результат. Отдельно считаются критические ложные зачёты и перенос на новый случай. Технические проверки RC2/офлайн-пакет фиксируются в docs/release-readiness.md.`,true);
  text(s,'Измерить цену корректного разбора\nдля преподавателя',64,169,1130,133,48,COLORS.white,true);
  text(s,'20%',64,353,382,127,100,COLORS.light,true);
  text(s,'целевой ориентир пилота,\nпока без результата',495,381,680,104,32,COLORS.white);
  text(s,'Сначала согласовать рубрику и провести занятие на целевых ПК',64,552,1125,69,28,COLORS.light);
}

const draft=path.join(BUILD,'kontur-dds-v3.draft.pptx');
await (await PresentationFile.exportPptx(presentation)).save(draft);
for(let i=0;i<presentation.slides.items.length;i++){
  const png=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const finalPath=process.env.DECK_OUTPUT_PATH||path.join(OUT,'kontur-dds-defense-v3.pptx');
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,
  pythonExecutable:path.join(RUNTIME,'python/bin/python3'),
  integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...([6,7,8,9].flatMap(n=>['--require-native-table-slide',String(n)]))],
  requiredNativeTableOwnerSlides:[6,7,8,9],explicitTotalSlideCount:11,
  fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,
  receiptPath:process.env.DECK_RECEIPT_PATH||path.join(BUILD,'validation-v3.json')});
console.log(JSON.stringify({finalPath,result}));
