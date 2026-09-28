# Уведомления о сторонних компонентах frontend

Снято с фактически установленных пакетов 19 сентября 2026. Это копии notices для включения в поставку интерфейса, не лицензия авторского кода проекта и не полный SBOM.

## React19.2.8, React DOM19.2.8, Scheduler0.27.0

Во всех трёх пакетах одинаковый текст LICENSE; приведён один раз.

```text
MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## lucide-react0.468.0

```text
ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

## Отдельные пакеты

Backend Python-дистрибутивы содержат свои dist-info/licenses в venv. Локальный llama-server поставляется с LLAMA_CPP_LICENSE, LLAMA_CPP_VENDORS_LICENSE, CPP_HTTPLIB_LICENSE, DLPACK_LICENSE, FMT_LICENSE, GO_LICENSE, MLX_LICENSE, MLX_C_LICENSE, PICOJSON_LICENSE, XGRAMMAR_LICENSE и XGRAMMAR_NOTICE; они находятся рядом с бинарниками runtime/local-ai. Этот каталог исключён из Git.

В локальном Qwen README указана Apache-2.0 и ссылка на upstream LICENSE, но отдельный текст LICENSE рядом с скачанными весами отсутствует. Полная поставка моделей и её notices не собраны в этом документе. macOS Milena вызывается как установленный системный голос; её runtime не копируется в контейнер.
