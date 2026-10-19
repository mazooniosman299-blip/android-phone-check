import re
import subprocess
from pathlib import Path
import shutil


class ADB:
    def __init__(self):
        local = Path(__file__).resolve().parent / 'platform-tools' / 'adb.exe'
        self.executable = str(local) if local.exists() else shutil.which('adb')

    def run(self, *args):
        if not self.executable:
            raise RuntimeError('ثبّت Android Platform Tools من Google وضع مجلد platform-tools بجوار البرنامج أو أضف adb إلى PATH.')
        result = subprocess.run([self.executable, *args], capture_output=True,
                                encoding='utf-8', errors='replace', timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'فشل الاتصال بالهاتف')
        return result.stdout.strip()

    def devices(self):
        return [line.split()[:2] for line in self.run('devices').splitlines()[1:] if line.strip()]

    def shell(self, serial, *args):
        return self.run('-s', serial, 'shell', *args)


def battery_values(text):
    values = {}
    for line in text.splitlines():
        if ':' in line:
            key, value = line.strip().split(':', 1)
            values[key] = value.strip()
    return values


def summarize(battery, memory, storage):
    notes = []
    try:
        temperature = int(battery['temperature']) / 10
        if temperature >= 45:
            notes.append('حرارة البطارية مرتفعة (45° أو أكثر). أوقف الشحن والأحمال الثقيلة واترك الهاتف يبرد.')
    except (KeyError, ValueError):
        pass
    if battery.get('health') in {'3', '4', '5', '6'}:
        notes.append('النظام يبلغ عن حالة بطارية غير جيدة؛ يوصى بفحصها لدى فني.')
    total = re.search(r'MemTotal:\s+(\d+)', memory)
    available = re.search(r'MemAvailable:\s+(\d+)', memory)
    if total and available and int(total[1]) and int(available[1]) / int(total[1]) < .1:
        notes.append('الذاكرة المتاحة أقل من 10% في هذه اللحظة؛ قد يؤثر ذلك على الاستجابة.')
    percentages = re.findall(r'(\d+)%', storage)
    if percentages and int(percentages[-1]) >= 90:
        notes.append('التخزين مستخدم بنسبة 90% أو أكثر. حرّر مساحة على الهاتف.')
    return notes or ['لم تظهر مؤشرات التحذير المحددة في القراءات المتاحة. هذه النتيجة لا تستبعد أعطال العتاد أو البرامج.']


def collect(adb, serial):
    errors = []

    def read(*args):
        try:
            return adb.shell(serial, *args)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            errors.append(' '.join(args) + ': ' + str(exc))
            return ''

    model = read('getprop', 'ro.product.model')
    android = read('getprop', 'ro.build.version.release')
    patch = read('getprop', 'ro.build.version.security_patch')
    battery = battery_values(read('dumpsys', 'battery'))
    memory = read('cat', '/proc/meminfo')
    storage = read('df', '-h', '/data')
    cpu = read('dumpsys', 'cpuinfo')
    return dict(serial=serial, model=model, android=android, security_patch=patch,
                battery=battery, memory=memory, storage=storage, cpu=cpu,
                notes=summarize(battery, memory, storage), errors=errors)
