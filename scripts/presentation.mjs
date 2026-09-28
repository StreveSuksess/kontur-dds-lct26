import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';

const ROOT=process.cwd();
const SKILL=process.env.PRESENTATION_SKILL_DIR||path.join(os.homedir(),'.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations');
const RUNTIME=process.env.PRESENTATION_RUNTIME_DIR||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const BUILD=path.join(ROOT,'runtime/presentation-build');
const OUT=path.join(ROOT,'deliverables');
const finalize=process.argv.includes('--final');
const revision=process.env.DECK_REVISION||'v1';
const {resolvePresentationFont,finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const FONT=resolvePresentationFont({fontFamily:'Arial'});
const fontPolicy={basis:'design',families:[FONT]};
const C={ink:'#203538',accent:'#3D6E61',paper:'#F7F9F6',muted:'#61736D',line:'#D7E0D8',soft:'#E8EFE8',white:'#FFFFFF',light:'#BED3C4'};
await fs.mkdir(BUILD,{recursive:true});await fs.mkdir(OUT,{recursive:true});
const load=JSON.parse(await fs.readFile(path.join(ROOT,'docs/load-test-results.json'),'utf8'));
const bench=JSON.parse(await fs.readFile(path.join(ROOT,'docs/benchmark-results.json'),'utf8'));
const qa='https://drive.google.com/file/d/1qpYkmGuSVKPBrBQgC_WB5luTcDzr0ZW9/view';
const p=Presentation.create({slideSize:{width:1280,height:720}});
let serial=0;
function txt(s,text,x,y,w,h,size=27,color=C.ink,bold=false){const b=s.shapes.add({geometry:'textbox',name:`text-${++serial}`,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});b.text=text;b.text.style={typeface:FONT,fontSize:size,bold,color,autoFit:'none',insets:{left:0,right:0,top:0,bottom:0},verticalAlignment:'top'};return b;}
function slide(title,notes='',dark=false){const s=p.slides.add();s.background.fill=dark?C.ink:C.paper;if(title)txt(s,title,64,50,1152,94,46,dark?C.white:C.ink,true);txt(s,String(p.slides.items.length).padStart(2,'0'),1170,665,48,25,18,dark?C.light:C.muted);s.speakerNotes.textFrame.setText(notes);return s;}
function caption(s,text,dark=false){txt(s,text,64,628,1100,40,20,dark?C.light:C.muted);}
function table(s,values,{x=64,y=168,w=1152,h=365,widths=[300,390,462],fontSize=24}={}){const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});t.borders.assign({style:'solid',fill:C.line,width:1});for(let r=0;r<values.length;r++){t.rows[r].height=h/values.length;for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill=r===0?C.ink:C.white;cell.text.style={typeface:FONT,fontSize,bold:r===0,color:r===0?C.white:C.ink,autoFit:'none',verticalAlignment:'middle',insets:{left:16,right:16,top:12,bottom:12}};}}return t;}
async function screenshot(s,kind){const file=process.env[kind==='workspace'?'WORKSPACE_SCREENSHOT':'REPORT_SCREENSHOT']||path.join(OUT,'assets',kind==='report'?'report-evidence.png':'workspace-viewport.png');try{const bytes=await fs.readFile(file);const added=s.images.add({blob:new Uint8Array(bytes),contentType:'image/png',alt:kind==='workspace'?'Фактический экран АРМ обучающегося КонтурДДС':'Фактический разбор учебной попытки КонтурДДС',fit:'contain',position:{left:64,top:164,width:842,height:445}});return true;}catch(e){if(finalize)throw new Error('Missing required real screenshot: '+file);txt(s,'Место для фактического экрана MVP\nВнутренний черновик',100,300,740,140,32,C.muted);return false;}}

// 1. Minimal cover; editable typography, no fabricated visual assets.
{
const s=slide('',`КонтурДДС — учебный прототип, не действующая система 112. Основания: docs/product-spec.md и Q&A заказчика. Заявленные эффекты обучения ещё не проверены на людях.`,true);
txt(s,'КонтурДДС',64,184,1140,120,84,C.white,true);
txt(s,'Тренажёр работы диспетчера\nпо готовой карточке происшествия',68,330,1000,132,40,C.light);
txt(s,'Локальное занятие · исходящий доклад · разбор преподавателем',68,557,1110,50,25,C.white);
}
// 2. Product scope is driven by customer evidence.
{
const s=slide('Задача диспетчера ДДС',`Источник: Q&A ${qa}, 17:42–18:53, 21:41–24:11, 39:12–43:19. Фокус: готовая карточка, исходящий доклад. АРМ должен повторять предоставленные поля/цвета: 25:15–27:47. 30с/3мин — изменяемые учебные ориентиры, не нормативная сертификация. Пользовательские интервью не проводились.`);
txt(s,'Учащийся получает готовую карточку\nи отрабатывает весь цикл реагирования',64,160,1120,110,37,C.ink,true);
const rows=[['01','Принять карточку','Открыть, проверить сведения и зафиксировать принятие'],['02','Передать сведения','Набрать учебный номер и сделать исходящий доклад'],['03','Завершить работу','Внести статусы, комментарии и итог']];
rows.forEach((r,i)=>{let y=322+i*94;txt(s,r[0],64,y,70,44,32,C.accent,true);txt(s,r[1],156,y,355,42,29,C.ink,true);txt(s,r[2],545,y,656,66,25,C.muted);});
caption(s,'Основание: материалы заказчика и запись Q&A. Первичный приём звонка гражданина — вне текущего MVP.');
}
// 3. Teaching workflow, flat composition.
{
const s=slide('Один цикл для преподавателя',`Основание: docs/product-spec.md, docs/api-contract.md; Q&A 14:00 и 37:00–38:00 про контроль преподавателя, 53:10–54:55 про назначения. Не утверждать наличие педагогического пилота. Версия сценария фиксируется в снимке попытки.`);
const rows=[['Подготовить','Выбрать шаблон или получить локальный AI-черновик'],['Утвердить','Проверить факты, критерии и эталон до назначения'],['Назначить','Выбрать учащихся и наблюдать учебные попытки'],['Разобрать','Проверить доказательства, скорректировать результат с причиной'],['Повторить','Назначить новую отработку нужного навыка']];
rows.forEach((r,i)=>{let y=165+i*82;txt(s,String(i+1),64,y,65,44,31,C.accent,true);txt(s,r[0],145,y,285,42,29,C.ink,true);txt(s,r[1],462,y,750,67,26,C.muted);});
caption(s,'Преподаватель управляет заданием и итогом. Изменение сценария не переписывает уже начатую попытку.');
}
// 4. Authentic UI evidence.
{
const s=slide('Рабочее место диспетчера',`Фактический экран работающего MVP; источник deliverables/assets/workspace-viewport.png. Предоставленные заказчиком скриншоты АРМ использованы как референс полей, состояний и цветов. Это программный учебный телефон; физическая SIP-интеграция не проверена. Q&A 10:35–11:10 допускает компьютерный симулятор.`);
await screenshot(s,'workspace');
txt(s,'Узнаваемая карточка',945,180,274,85,28,C.ink,true);txt(s,'Поля, статусы и история действий',945,265,274,105,25,C.muted);
txt(s,'Исходящий доклад',945,395,274,70,28,C.ink,true);txt(s,'Учебный номер, голосовая реплика и запись ответа',945,477,274,114,25,C.muted);
caption(s,'Снимок работающего прототипа. Учебные данные; звонки на реальные номера отсутствуют.');
}
// 5. Evidence + human review.
{
const s=slide('Разбор с доказательствами',`Фактический экран: deliverables/assets/report-evidence.png. Исходный PNG сохранён без изменения содержимого. Оценивание: docs/product-spec.md и backend/app/assessment. Время, статусы и номер проверяются правилами; текстовая семантика ограничена. Спорные случаи направляются преподавателю. Не заявлять полноту проверки фактического смысла. ASR не равен ответу ученика — текст перед сдачей подтверждается.`);
await screenshot(s,'report');
txt(s,'За что замечание',945,180,274,80,28,C.ink,true);txt(s,'Событие, текст и ожидаемое действие',945,265,274,105,25,C.muted);
txt(s,'Кто решает',945,395,274,70,28,C.ink,true);txt(s,'Преподаватель подтверждает или меняет итог с причиной',945,477,274,120,25,C.muted);
caption(s,'Ошибка распознавания не должна становиться ошибкой учащегося. Спорный смысл требует проверки.');
}
// 6. Architecture as editable evidence table, not a decorative drawing.
{
const s=slide('Локальная работа и границы AI',`Реальное исполнение: docs/local-ai.md, docs/local-ai-validation.json и docs/local-ai-generation-validation.json. Whisper-small CPU; Qwen3 1.7B Q4_K_M CPU4, llama-server loopback11434; ASR11435. Нейросетевой анализ показал максимум3/6 на синтетических примерах и не используется как окончательная оценка. Узкая генерация3/3 — маленькая настроечная выборка, не доказательство общей точности. Linux/x86 и физический РТУ не проверены.`);
table(s,[['Компонент','Что делает','Граница ответственности'],['React + FastAPI','Карточки, назначения, журнал, разбор','Данные и действия сохраняются локально'],['Whisper small','Доклад 9,7 с обработан за 2,8 с','Учащийся подтверждает текст'],['Qwen3 1.7B','Предлагает черновик учебного текста','Факты проверяются; утверждает преподаватель']]);
txt(s,'LLM-анализ: 3/6 примеров. Итог подтверждает преподаватель',64,568,1130,58,31,C.accent,true);
caption(s,'Локальные модели. Замер ASR: один синтетический WAV на Mac 48 ГБ; целевая конфигурация ещё не проверена.');
}
// 7. Market positioning with careful source attribution.
{
const s=slide('Рынок и выбранный фокус',`Публичные материалы вендоров, не наше испытание: https://911trainer.com/ ; https://equature.com/solutions/smartsim ; https://www.sklls.ai/ ; https://www.eventidecommunications.com/critical-insights-ai-training-simulator/ . Российские учебные комплексы: https://www.umcgo.ru/8-main-menu.html и https://sibpsa.ru/sveden/objects/ . Подробнее docs/product-research.md и memory-bank/research/2026-09-19-market-research.md. Наличие аналога или неупоминание функции не доказывает отсутствие/наличие offline у конкретного продукта.`);
table(s,[['Категория','Примеры','Вывод для продукта'],['Учебные АРМ 112','Звенигород, Сибирская академия','Учебная инфраструктура уже существует'],['CAD и телефонные симуляторы','9-1-1 Reality, Equature SmartSim','Нужен полный рабочий цикл'],['AI-тренажёры','Sklls, Eventide','AI-сценарии и рубрики уже есть на рынке']],{h:354});
txt(s,'Наш фокус — сценарий работы московской ДДС',64,562,1150,52,30,C.accent,true);
caption(s,'Поля АРМ, исходящий доклад и локальный разбор по материалам заказчика. Уникальность категории не заявляется.');
}
// 8. Actual measurements, dynamically loaded rather than stale counts.
{
const s=slide('Что уже измерено',`Источники: docs/load-test-results.json, generated_at=${load.generated_at}; docs/benchmark-results.json, generated_at=${bench.generated_at}. Нагрузка: короткий API burst, один worker, SQLiteWAL, macOS arm64/48GB. Не измерялись отрисовка UI, длительная эксплуатация или100людей. Benchmark: synthetic development seed, неслепая и неметодистская выборка. Unsupported не считается верным ответом. Тесты проекта меняются, их количество на слайд не вынесено.`);
table(s,[['Проверка','Измерение','Границы вывода'],['API: 100 учётных записей',`p95 ${Math.round(load.read_100_users.p95_ms)} мс; ${load.read_100_users.errors} ошибок`,'Короткая серия API-запросов'],['20 активных попыток',`${load.persistence.stored_status_events}/${load.persistence.expected_status_events} событий сохранено`,'Все события этого прогона'],['Синтетические проверки',`${bench.exact_matches}/${bench.assertions_supported} точных совпадений`,`${bench.assertions_total-bench.assertions_supported} из ${bench.assertions_total} проверок ещё не поддержаны`]],{h:348,widths:[390,330,432]});
txt(s,'Измерения прототипа ≠ доказанный эффект обучения',64,558,1140,60,32,C.accent,true);
caption(s,'На целевом i5/16 ГБ, в живом классе и на независимых экспертных ответах проверок ещё не было.');
}
// 9. Learning validity before broad rollout.
{
const s=slide('План проверки с учебным центром',`Предложение, не выполненные исследования. docs/product-research.md и memory-bank/research/2026-09-19-evaluation-design.md. 2–3методиста,5–8представителейролей — состав для обсуждения, не набранные участники. Размер учебного пилота определяется после baseline, без необоснованных обещаний статистической значимости.`);
const rows=[['Предметная проверка','Методисты согласуют сценарии, статусы и критические ошибки'],['Проверка интерфейса','Представители ролей выполняют занятие без подсказок разработчика'],['Независимая оценка','Два эксперта размечают закрытый набор; сравниваем ошибки системы'],['Учебный пилот','Измеряем разбор преподавателя и перенос навыка на новые задания']];
rows.forEach((r,i)=>{let y=172+i*102;txt(s,r[0],64,y,395,72,29,C.ink,true);txt(s,r[1],510,y,705,80,27,C.muted);});
caption(s,'Сначала исходные замеры и согласие экспертов. Пользовательский пилот пока не проведён.');
}
// 10. Explicit request and target, not claimed savings.
{
const s=slide('Следующий шаг — пилот',`Целевая гипотеза из docs/product-research.md: снижение медианного времени преподавателя на20% без ухудшения выявления критических ошибок. Это цель для обсуждения, не измеренный результат. Требуются представитель учебного центра, методист, выбранные службы, целевые компьютеры и согласованная рубрика. Реальная SIPинтеграция/закрытыйконтур — отдельный этап внедрения.`,true);
txt(s,'Проверить экономию времени\nна корректно разобранной попытке',64,168,1140,130,47,C.white,true);
txt(s,'−20%',64,348,400,132,100,C.light,true);txt(s,'целевой ориентир пилота,\nне достигнутый результат',492,378,708,96,32,C.white);
txt(s,'Для старта: методист, две службы и целевой учебный класс',64,552,1140,65,29,C.light);
}

const draft=path.join(BUILD,`kontur-dds-${revision}.draft.pptx`);
await (await PresentationFile.exportPptx(p)).save(draft);
await fs.writeFile(path.join(BUILD,'presentation.json'),JSON.stringify(p.toProto()));
for(let i=0;i<p.slides.items.length;i++){const slide=p.slides.items[i];const png=await p.export({slide,format:'png',scale:1});await fs.writeFile(path.join(BUILD,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));}
if(finalize){const output=path.join(OUT,`kontur-dds-defense-${revision}.pptx`);const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath:output,pythonExecutable:path.join(RUNTIME,'python/bin/python3'),integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','6','--require-native-table-slide','7','--require-native-table-slide','8'],requiredNativeTableOwnerSlides:[6,7,8],explicitTotalSlideCount:10,fontPolicy,verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation-${revision}.json`)});console.log(JSON.stringify(result));}
console.log(JSON.stringify({draft,slides:p.slides.items.length,finalized:finalize,previewDirectory:BUILD}));
