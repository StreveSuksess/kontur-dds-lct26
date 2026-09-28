# API тренажёра: RC1 и контракт RC2

RC1 упакован отдельно. Ниже описан текущий контракт исходного кода, включая покритериальный разбор RC2. Полный backend-регрессионный прогон, клиентская сборка и браузерный путь RC2 проверены; состояние отдельного архива указано в [готовности релиза](release-readiness.md). Исходный отчёт правил остаётся доступен после решения преподавателя.

Все пути /api. JSON snake_case. Время ISO8601 UTC. Идентификаторы строковые UUID. Ошибка: {detail: string}. Cookie session; fetch credentials include. Локальная разработка через Vite proxy, production same origin. Списки возвращают массивы, classifier — объект ниже.

## Общие типы

User = {id, username, name, role: "student"|"teacher"|"admin", service, group_name, active:boolean}.

Card = {number:string, address:string, description:string, incident_type:string, incident_code:string, caller_name:string, caller_phone:string, casualties:"unknown"|"no"|"yes", services:string[]}.

Contact = {id:string, name:string, role:string, phone:string, greeting:string, reply:string}. В student view скрывается reply до диалога; greeting выдаётся после соединения.

Scenario = {id,title,description,service,difficulty:"basic"|"intermediate"|"advanced",objective,status:"draft"|"approved"|"archived",version:number,owner_id,card:Card,contacts:Contact[],expected_statuses:string[],required_facts:[{id,label,patterns:string[],critical:boolean,confirmed_by_contact_ids?:string[]}],reference_response:string,response_limit_seconds:number,completion_limit_seconds:number,source_note:string,created_at,updated_at}. Статусы действий: accepted, rejected, responding, arrived, working, refused, completed. `completion_limit_seconds` — сохранённое для совместимости имя поля; теперь это срок **первого статуса с непустым текстом**, а не закрытия происшествия. expected_statuses — учебная последовательность, не универсальный регламент.

Session = {id,scenario_id,scenario_title,scenario_version,student_id,student_name,teacher_id,service,mode:"practice"|"exam",status:"assigned"|"active"|"submitted"|"reviewed"|"stopped",assigned_at,started_at:null|string,finished_at:null|string,card:Card,contacts:PublicContact[],objective,response_limit_seconds,completion_limit_seconds,current_status:null|string,draft:object,events:Event[],report:null|Report}.

PublicContact = {id,name,role,phone}. Student Session НЕ содержит reference_response, required_facts, expected_statuses, reply и внутренний snapshot. Teacher view может содержать поле scenario_snapshot.

Event = {id,client_event_id,kind,at,elapsed_seconds,payload:object}. Виды от клиента: card_opened, status_changed, call_started, call_ended, trainee_message, hint_used, connection_restored. Сервер добавляет session_started, contact_message, draft_saved, session_submitted, teacher_stopped, review_saved и criterion_review_saved. payload status_changed = {status,comment}; `comment` обязателен и непуст. call_started={phone}; trainee_message={text,call_id}; hint_used={hint}; connection_restored={offline_seconds}. Ограничение длины comment/text 1999.

Report = {score:number,max_score:100,requires_review:boolean,critical_errors:number,summary:string,mode:"rules"|"hybrid",reaction_seconds:null|number,first_update_seconds:null|number,duration_seconds:number,criteria:Criterion[],strengths:string[],recommendations:string[],teacher_review:null|{score:number,comment:string,reviewed_at:string,reviewer_name:string},generated_at:string}. `first_update_seconds` отсчитывается от серверного поступления карточки/начала попытки до первого сохранённого статуса с текстом. `duration_seconds` — фактическая полная длительность попытки без трёхминутного лимита.

В RC2 Report может дополнительно содержать `criterion_review_revision:number`, `criterion_reviews:{[criterion_id]:CriterionDecision}`, `expert_assessment:{score:number,max_score:number,requires_review:boolean,critical_errors:number}` и `teacher_review_stale:boolean`. `CriterionDecision = {status:"pass"|"fail"|"review",comment:string,evidence_ids:string[],reviewed_at:string,reviewer_name:string,revision:number}`. В `teacher_review` появляется `criterion_revision:number`. Отсутствующие поля означают старый отчёт без покритериальных решений; исходные `score`, `criteria`, `requires_review`, `generated_at` остаются прежними. `expert_assessment` рассчитывается по исходным весам и явным решениям; `pass` даёт максимум критерия, `fail` и `review` — 0. Наличие хотя бы одного `review` сохраняет `requires_review`, включая критерий с нулевым весом.

Criterion = {id,title,category:"timing"|"workflow"|"communication"|"content"|"grammar",status:"pass"|"fail"|"review",points:number,max_points:number,critical:boolean,actual:string,expected:string,explanation:string,evidence_ids:string[],source:string}.

## Аутентификация

GET /auth/me -> User (401 если нет сессии)
POST /auth/login {username,password} -> User; ставит cookie
POST /auth/logout {} -> {ok:true}; удаляет cookie
GET /meta -> {name:"Контур ДДС",demo_mode:boolean,version:string,ai_mode:string,status_labels:{accepted:"Принята",...},services:string[]}
Демо при DEMO_MODE=true: teacher / Demo112!, student / Demo112!, admin / Demo112!. Все синтетические. Production не создаёт известные пароли.

## Сценарии — teacher only

GET /scenarios -> Scenario[] (свои+seed копируемые)
GET /scenarios/{id} -> Scenario
POST /scenarios -> Scenario (поля без id/version/owner/даты; всегда draft)
PUT /scenarios/{id} -> Scenario (увеличить version, сбросить approve)
POST /scenarios/{id}/approve {} -> Scenario (проверить карточку/контакты/эталон/критерии)
POST /scenarios/{id}/duplicate {} -> Scenario (новый draft своего владельца)
POST /scenarios/generate {incident_code,service,difficulty,instructions} -> Scenario (новый draft; generator_mode через response/header либо source_note)
POST /scenarios/{id}/archive {} -> Scenario

## Учебный процесс

GET /users -> User[] (teacher видит учеников; admin всех)
POST /sessions {scenario_id,student_ids:string[],mode} -> Session[] (teacher; только approved, профиль службы совпадает или универсальный)
POST /sessions/arrive {session_ids:string[]} -> Session[] (teacher; атомарная одновременная доставка от 1 до 100 своих назначенных карточек; все получают один серверный `started_at`; учащийся видит часы ожидающих карточек)
GET /sessions -> Session[] (student только свои; teacher только свои назначения; admin403)
GET /sessions/{id} -> Session (тот же scope; report только после submitted/reviewed/stopped)
POST /sessions/{id}/start {} -> Session (student owner; идемпотентно)
PUT /sessions/{id}/draft {draft:object} -> {saved_at:string} (student active; допускаются comment, selected_status, phone, message)
POST /sessions/{id}/events {client_event_id:string,kind:string,payload:object} -> {event:Event,session:Session,reply:null|{text:string,call_id:string}}. Повтор ID возвращает предыдущий результат без второго события/ответа. call_started выдаёт greeting; trainee_message выдаёт reply из сценария/локальной модели. Неверный учебный номер фиксируется как событие с connected=false; реальные сети не вызываются.
POST /sessions/{id}/submit {} -> Session (student owner active, фиксирует конец и создаёт Report, идемпотентно)
POST /sessions/{id}/stop {} -> Session (teacher owner; status stopped, отчёт помечен прерванным)
POST /sessions/{id}/review {score:number,comment:string,expected_criterion_revision?:number} -> Session (teacher owner; только завершённые, обязательная причина, исходный Report сохраняется). При наличии покритериальных решений `expected_criterion_revision` обязателен и должен совпадать с текущим; иначе 409 без изменения отчёта. Запись фиксирует ревизию и снимает `teacher_review_stale`.
POST /sessions/{id}/criterion-reviews {criterion_id:string,status:"pass"|"fail"|"review",comment:string,evidence_ids?:string[],expected_criterion_revision?:number} -> Session (teacher owner; только submitted/reviewed/stopped). `criterion_id` должен быть в исходном `report.criteria`; основание после удаления пробелов — 3–1999 символов. До 50 уникальных `evidence_ids`, каждый ID — событие этой попытки; при отсутствии поля копируются ID исходного критерия. Неизвестный критерий или чужое событие — 422, активная попытка — 409, чужая роль/назначение — 403. После первой коррекции текущая ревизия обязательна и должна совпадать: конфликт возвращает 409 без записи. Каждый пересмотр сохраняет `previous`/`current` в событии и увеличивает ревизию. Если общий итог уже был подтверждён, он становится устаревшим; ранее reviewed возвращается в submitted до повторного подтверждения. Остановленная попытка остаётся stopped.
POST /sessions/{id}/repeat {} -> Session (teacher owner или student owner practice; новый ID, без старых событий)
GET /sessions/{id}/export.csv -> CSV (тот же scope; UTF8 BOM, защита от формул ячеек). RC2 выводит раздельно автоматический, экспертный и покритериальный баллы, флаг устаревшего итога, ревизию, исходное и действующее решение каждого критерия, основание, доказательства, автора и время; исторические исходные поля не заменяются.
GET /analytics -> {total_sessions,completed_sessions,active_sessions,scored_sessions,pending_review_sessions,stopped_sessions,average_score:null|number,average_reaction_seconds:null|number,criteria:[{id,title,failed,total}],recent_sessions:Session[]} (teacher/student scoped). `average_score` использует только допустимые подтверждённые баллы, а `criteria` — только пригодные покритериальные сведения. Остановленные попытки не входят в обе оценки; `scored_sessions` — знаменатель среднего балла. `completed_sessions` означает завершённые пригодные, включая ожидающие проверки; `pending_review_sessions` — завершённые без доверенного итогового балла. Критерии с одинаковым ID, но разными названиями агрегируются отдельно.

## Отдельное текстовое упражнение 112

GET /intake112/cases -> {services:string[],cases:[{id,title,statement}]} (student/teacher; эталоны скрыты до сдачи)
GET /intake112/attempts -> Attempt112[] (student — только свои; teacher — группа, максимум 100 последних)
POST /intake112/attempts {case_id,card:{incident_type,address,description,caller_name,caller_phone,services:string[]}} -> Attempt112 (student; две фиксированные синтетические вводные, сравнение полей после нормализации, выбор служб по точному составу)
POST /intake112/attempts/{id}/review {comment:string} -> Attempt112 (teacher той же группы; обязательное заключение)

`Attempt112` содержит введённую карточку, список совпадений и расхождений с авторским эталоном, время сдачи и заключение преподавателя. Эталон показывается ученику после сдачи для разбора. Смысл свободного текста, правильность маршрутизации вне двух учебных вводных и живой голос этим API не проверяются.

## Справочник и администрирование

GET /classifier?q=&limit=30 -> {total:number,version:string,items:[{code,label,group,features:string[],primary_service:null|string,source_row:number}],warnings:string[]}
GET /classifier/{code} -> тот же item + {routing:object,source_file:string}
GET /knowledge -> [{id,title,body,source}]
GET /health -> {status:"ok",database:"ok",version,ai:{configured:boolean,mode:string},uptime_seconds:number}
GET /admin/status -> {users_count,sessions_count,audit_count,database_backend,ai_mode,backup_files:[],uptime_seconds} (admin)
GET /admin/audit -> [{id,actor_name,action,entity_type,entity_id,at,details}] (admin)
POST /admin/users {username,name,password,role,service,group_name} -> User
PATCH /admin/users/{id} {active:boolean} -> User (не блокировать себя)
POST /admin/backup {} -> {filename,created_at,bytes} (admin, локальный backup; не отправлять DB клиенту)

## Согласованность

Backend реализует разграничение доступа, неизменяемый снимок задания, утверждение сценария, идемпотентность событий, текстовые отрицания и тайминг. Frontend не подставляет фиктивные метрики, не читает скрытый эталон и не создаёт локальные оценки. Состояние проверок RC2 ведётся отдельно в [release-readiness.md](release-readiness.md).

## Локальные голосовые и языковые помощники

GET /ai/status (всеавторизованныероли) → {language_model:{configured,available,model},speech:{configured,available,model?},voice:{configured,available},assessment:"rules_with_teacher_review"}. Доступность проверяется реально по loopback health.
POST /sessions/{id}/transcribe (student owner active) raw audio/wav|webm|ogg|mp4 до10MiB → {text,language,duration_seconds,latency_seconds,model,requires_human_review:true,mode:"local_asr"}. Не создаёт событий и не сохраняет аудио. Ученик проверяет и отдельно отправляет текст.
GET /sessions/{id}/events/{event_id}/audio (student/teacher owner scope) → audio/wav. Только уже сохранённый contact_message этой попытки, без передачи произвольного текста от браузера.
POST /sessions/{id}/ai-review (teacher owner finished) → {mode:"local_llm"|"not_requested",message?:string,model,latency_seconds,suggestions:[{criterion_id,observation,quote,needs_review:true}],discarded_unsupported,requires_teacher_review:true,changes_grade:false}. Цитаты сверяются с текстом и ID критериев на сервере. Ответ модели не меняет журнал и баллы.

Генерация /scenarios/generate при AI_MODE=local использует ограниченную модель для title/card_description/contact_reply и сохраняет входные факты буквально. Факты/телефоны/статусы/рубрика остаются локальными настройками преподавателя. Недоступность или нарушение проверки → явно подписанный templates fallback.

## Уточнения после интеграционной проверки

`confirmed_by_contact_ids` — список ID контактов сценария, до10. Для зачёта нужен ответ любого выбранного контакта после доклада учащегося, подтверждающий факт, и затем собственное утверждение учащегося. Приветствие и более поздний ответ не оправдывают преждевременную запись; ссылки на отсутствующие контакты блокируют approve. По умолчанию список пустой, проверяется содержание.

AI-review экспериментален: только критерии со status=review и category=content/grammar. Если их нет, `not_requested`, latency0, suggestions[]: модель не вызывалась. Проверка quote отбрасывает несуществующие цитаты, но не доказывает корректность вывода.

`GET /recommendations` — student/teacher со scope собственных занятий. Минимум3 подходящих завершённых попытки, последние10; остановленные попытки не входят, неопределённые результаты требуют экспертной проверки. Возвращает объяснение, использованные попытки и совместимые утверждённые сценарии. Не назначает их автоматически. Поля и авторские пороги описаны вdocs/adaptation.md.

В RC2 появление `criterion_reviews` без актуального общего подтверждения исключает попытку из рекомендаций. Устаревшее общее подтверждение тоже не учитывается. Явные `pass`/`fail` могут служить свидетельством конкретного критерия после актуального подтверждения; общий исправленный балл сам по себе не подтверждает остальные критерии. Тот же принцип применяется в `GET /analytics`.
