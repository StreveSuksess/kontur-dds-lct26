import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile} from '@oai/artifact-tool';

// Separate RC2 deck. This generator never writes the RC1 presentation.
const ROOT=process.cwd();
const SKILL=process.env.PRESENTATION_SKILL_DIR||path.join(os.homedir(),'.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations');
const RUNTIME=process.env.PRESENTATION_RUNTIME_DIR||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const BUILD=path.join(ROOT,'runtime/presentation-v2-build');
const OUT=path.join(ROOT,'deliverables');
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const FONT=resolvePresentationFont({fontFamily:'Arial'});
const COLORS={ink:'#203538',accent:'#3D6E61',paper:'#F7F9F6',muted:'#61736D',line:'#D7E0D8',white:'#FFFFFF',light:'#BED3C4'};
const qa='https://drive.google.com/file/d/1qpYkmGuSVKPBrBQgC_WB5luTcDzr0ZW9/view';
const load=JSON.parse(await fs.readFile(path.join(ROOT,'docs/load-test-results.json'),'utf8'));
const bench=JSON.parse(await fs.readFile(path.join(ROOT,'docs/benchmark-results.json'),'utf8'));
const model=await fs.readFile(path.join(ROOT,'docs/model-comparison.md'),'utf8');
if(!model.includes('32/48')||!model.includes('четыре')&&!model.includes('4B'))throw new Error('Model comparison has changed; review slide 7');
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
  const s=slide('',`Источник: docs/product-research.md; Q&A ${qa}. RC2 — исходный код с адресным разбором. Инженерная и педагогическая проверка имеют разные статусы.`,true);
  text(s,'Контур ДДС',64,184,1140,120,84,COLORS.white,true);
  text(s,'Тренажёр работы по готовой\nкарточке происшествия',68,330,1080,132,40,COLORS.light);
  text(s,'Демонстрация прототипа и проверяемого разбора',68,557,1110,50,25,COLORS.white);
}
// 2: Product scope from customer Q&A.
{
  const s=slide('Учебная задача ДДС',`Q&A ${qa}, 17:42–18:51, 21:41–24:11, 39:12–43:19. См. docs/product-research.md. Задание начинается после оформления карточки 112; имитация первого звонка гражданина не входит в выбранный MVP.`);
  text(s,'Учащийся получает карточку и проходит\nрабочий цикл до завершения',64,162,1120,105,37,COLORS.ink,true);
  const sequence=[['01','Открыть карточку','Проверить сведения и зафиксировать принятие'],['02','Доложить','Связаться с учебным должностным лицом'],['03','Завершить','Сохранить статусы, комментарий и итог']];
  sequence.forEach((row,i)=>{const top=324+i*94;text(s,row[0],64,top,68,50,32,COLORS.accent,true);text(s,row[1],155,top,332,58,29,COLORS.ink,true);text(s,row[2],535,top,670,68,25,COLORS.muted);});
  caption(s,'Основание: материалы заказчика и Q&A. Учебные лимиты времени настраиваются преподавателем.');
}
// 3: Product position, without unsupported uniqueness claims.
{
  const s=slide('Рынок и выбранный фокус',`Публичные сведения поставщиков, не сравнительное испытание: https://911trainer.com/ ; https://equature.com/solutions/smartsim ; https://www.sklls.ai/ ; https://www.eventidecommunications.com/critical-insights-ai-training-simulator/ . Российские комплексы: https://www.umcgo.ru/8-main-menu.html ; https://sibpsa.ru/sveden/objects/ . Анализ и оговорки: docs/product-research.md.`);
  table(s,[['Категория','Примеры','Вывод для продукта'],['Учебные АРМ 112','Звенигород, Сибирская академия','Инфраструктура обучения уже существует'],['CAD и телефонные симуляторы','9-1-1 Reality, Equature','Нужен полный рабочий цикл'],['AI-тренажёры','Sklls, Eventide','Сценарии и рубрики есть на рынке']],{h:354});
  text(s,'Специализация: рабочий цикл московской ДДС',64,558,1152,54,30,COLORS.accent,true);
  caption(s,'Поля АРМ, исходящий доклад и локальный разбор. Уникальность категории не заявляется.');
}
// 4: Authentic prototype screen, explicitly labeled.
{
  const s=slide('Рабочее место диспетчера',`Фактический экран RC1 из deliverables/assets/workspace-viewport.png. Дизайн учебного АРМ основан на скриншотах, предоставленных заказчиком, и Q&A 25:15–27:47. Методист не проверял применимость к действующему рабочему АРМ. Программный учебный телефон без реальной SIP-сети.`);
  await shot(s,'workspace-viewport.png','Фактический экран АРМ обучающегося');
  text(s,'Готовая карточка',945,180,274,85,28,COLORS.ink,true);text(s,'Поля и статусы по\nскриншотам заказчика.\nМетодист ещё не проверял.',945,265,274,120,23,COLORS.muted);
  text(s,'Учебный доклад',945,401,274,70,28,COLORS.ink,true);text(s,'Номер контакта, реплика и ответ сохраняются в журнале',945,480,274,116,25,COLORS.muted);
  caption(s,'Снимок прототипа. Учебные данные. Применимость к рабочему АРМ пока не проверена.');
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
  const s=slide('Что измерено в прототипе',`Источники: docs/load-test-results.json generated_at=${load.generated_at}; docs/benchmark-results.json generated_at=${bench.generated_at}. Короткий HTTP API burst на Mac arm64/48ГБ, 1 worker SQLiteWAL. Синтетический development benchmark без независимой методистской разметки. Не измерялись browser rendering100users, живой класс, длительная нагрузка, перенос навыка.`);
  table(s,[['Проверка RC1','Измерение','Граница вывода'],['API: 100 пользователей',`p95 ${Math.round(load.read_100_users.p95_ms)} мс; ${load.read_100_users.errors} ошибок`,'Короткая серия запросов'],['20 активных попыток',`${load.persistence.stored_status_events}/${load.persistence.expected_status_events} событий`,'Все события этого прогона'],['Синтетический набор',`${bench.exact_matches}/${bench.assertions_supported} точных совпадений`,`${bench.assertions_total-bench.assertions_supported} из ${bench.assertions_total} не поддержаны`]],{h:352,widths:[390,330,432]});
  text(s,'Технические замеры не показывают эффект обучения',64,558,1150,54,30,COLORS.accent,true);
  caption(s,'Нужны целевой класс и экспертные данные. Проверки RC2 фиксируются отдельно от RC1.');
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

const draft=path.join(BUILD,'kontur-dds-v2.draft.pptx');
await (await PresentationFile.exportPptx(presentation)).save(draft);
for(let i=0;i<presentation.slides.items.length;i++){
  const png=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
const finalPath=process.env.DECK_OUTPUT_PATH||path.join(OUT,'kontur-dds-defense-v2.pptx');
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,
  pythonExecutable:path.join(RUNTIME,'python/bin/python3'),
  integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...([3,5,6,7,8].flatMap(n=>['--require-native-table-slide',String(n)]))],
  requiredNativeTableOwnerSlides:[3,5,6,7,8],explicitTotalSlideCount:10,
  fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,
  receiptPath:process.env.DECK_RECEIPT_PATH||path.join(BUILD,'validation-v2.json')});
console.log(JSON.stringify({finalPath,result}));
