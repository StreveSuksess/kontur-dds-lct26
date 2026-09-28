"""Download independently published official sources with certificate verification."""
import hashlib
from pathlib import Path
import urllib.request
import truststore
truststore.inject_into_ssl()
import kagglehub

# Required conversion inputs. The whole-bundle API hit an error on an optional file.
for filename in ('config.json', 'generation_config.json', 'merges.txt',
                 'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors',
                 'model.safetensors.index.json', 'tokenizer.json', 'tokenizer_config.json', 'README.md'):
    print(kagglehub.model_download('qwen-lm/qwen-3/transformers/1.7b/1', path=filename), flush=True)
checksum = '9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794'
path = Path('models/local-ai/whisper-small.pt')
if not path.exists():
    temporary = path.with_suffix('.download')
    urllib.request.urlretrieve(f'https://openaipublic.azureedge.net/main/whisper/models/{checksum}/small.pt', temporary)
    if hashlib.file_digest(temporary.open('rb'), 'sha256').hexdigest() != checksum:
        temporary.unlink()
        raise ValueError('Whisper checksum mismatch')
    temporary.rename(path)
if hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != checksum:
    raise ValueError('Whisper checksum mismatch')
print(path, flush=True)
