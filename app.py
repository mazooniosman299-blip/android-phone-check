import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timezone
from diagnostics import ADB, collect


class App:
    def __init__(self, root):
        self.root = root
        self.adb = ADB()
        self.report = None
        self.devices = {}
        root.title('فاحص أندرويد — USB')
        root.geometry('1000x720')
        root.minsize(800, 600)
        ttk.Label(root, text='فاحص أندرويد', font=('Segoe UI', 24, 'bold'), anchor='e').pack(fill='x', padx=24, pady=12)
        ttk.Label(root, text='وصّل الهاتف بكابل بيانات، فعّل USB debugging، ووافق على الاتصال من شاشة الهاتف.', anchor='e').pack(fill='x', padx=24)
        bar = ttk.Frame(root)
        bar.pack(fill='x', padx=24, pady=16)
        self.selector = ttk.Combobox(bar, state='readonly', width=46)
        self.selector.pack(side='right', padx=6)
        self.buttons = []
        self.button(bar, 'تحديث الأجهزة', self.refresh)
        self.button(bar, 'بدء الفحص', self.scan)
        self.status = tk.StringVar(value='جاهز للاتصال')
        ttk.Label(root, textvariable=self.status, anchor='e').pack(fill='x', padx=24)
        self.output = tk.Text(root, wrap='word', font=('Segoe UI', 11), padx=15, pady=15)
        self.output.pack(fill='both', expand=True, padx=24, pady=12)
        self.output.tag_configure('rtl', justify='right')
        self.output.configure(state='disabled')
        actions = ttk.Frame(root)
        actions.pack(fill='x', padx=24, pady=14)
        self.button(actions, 'حفظ تقرير JSON', self.save)
        self.button(actions, 'إعدادات تحديث النظام', lambda: self.settings('android.settings.SYSTEM_UPDATE_SETTINGS'))
        self.button(actions, 'إعادة ضبط المصنع…', self.reset)
        self.write('لا يتم تنزيل تحديثات أو مسح بيانات تلقائياً.\nالفحص يعرض قراءات النظام الحالية؛ ليس اختبار أداء معياريًا ولا كشفًا شاملاً للأعطال.\nنسبة الشحن لا تعني نسبة صحة البطارية أو سعتها المتبقية.')

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side='right', padx=5)
        self.buttons.append(button)

    def write(self, text):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('end', text, 'rtl')
        self.output.configure(state='disabled')

    def background(self, task, done):
        for button in self.buttons:
            button.configure(state='disabled')
        self.status.set('جارٍ التنفيذ…')

        def work():
            try:
                result = task()
                self.root.after(0, lambda: finish(result, None))
            except Exception as exc:
                self.root.after(0, lambda error=str(exc): finish(None, error))

        def finish(result, error):
            for button in self.buttons:
                button.configure(state='normal')
            self.status.set('تعذّر التنفيذ' if error else 'اكتمل')
            if error:
                messagebox.showerror('خطأ', error)
            else:
                done(result)
        threading.Thread(target=work, daemon=True).start()

    def selected(self):
        serial = self.devices.get(self.selector.get())
        if not serial:
            messagebox.showinfo('الاتصال', 'حدّث الأجهزة واختر هاتفًا مصرحًا له أولاً.')
        return serial

    def refresh(self):
        def done(devices):
            self.devices = {serial: serial for serial, state in devices if state == 'device'}
            self.selector['values'] = list(self.devices)
            self.selector.set(next(iter(self.devices), ''))
            self.write('\n'.join(f'{serial}: {state}' for serial, state in devices) or 'لا توجد أجهزة. تحقق من الكابل وتعريف USB الخاص بالشركة المصنعة.')
            if any(state == 'unauthorized' for _, state in devices):
                messagebox.showinfo('السماح بالاتصال', 'افتح شاشة الهاتف ووافق على بصمة الكمبيوتر. لن يتجاوز التطبيق قفل الهاتف.')
        self.background(self.adb.devices, done)

    def scan(self):
        serial = self.selected()
        if not serial:
            return

        def done(report):
            report['captured_at'] = datetime.now(timezone.utc).isoformat()
            self.report = report
            battery = report['battery']
            try:
                temperature = f"{int(battery['temperature']) / 10:g} °C"
            except (KeyError, ValueError):
                temperature = 'غير متاح'
            health = {'1': 'غير معروف', '2': 'جيدة حسب النظام', '3': 'سخونة زائدة', '4': 'تالفة', '5': 'جهد زائد', '6': 'فشل غير محدد', '7': 'باردة'}.get(battery.get('health'), 'غير متاح')
            text = f"الجهاز: {report['model']}\nأندرويد: {report['android']}\nتاريخ التصحيح الأمني: {report['security_patch']}\nشحن البطارية: {battery.get('level', 'غير متاح')} / {battery.get('scale', 'غير متاح')}\nحرارة البطارية: {temperature}\nحالة البطارية: {health}\n\nالملاحظات:\n" + '\n'.join(report['notes'])
            text += '\n\nالتخزين:\n' + report['storage'] + '\n\nالذاكرة (kB):\n' + '\n'.join(report['memory'].splitlines()[:6])
            text += '\n\nعينة استخدام المعالج والعمليات (ليست benchmark):\n' + report['cpu']
            if report['errors']:
                text += '\n\nقراءات تعذّر الحصول عليها؛ الفحص جزئي:\n' + '\n'.join(report['errors'])
            self.write(text)
        self.background(lambda: collect(self.adb, serial), done)

    def settings(self, action):
        serial = self.selected()
        if serial:
            def done(result):
                if 'Error' in result or 'Exception' in result:
                    messagebox.showwarning('إعدادات الهاتف', 'الشركة المصنعة لا تدعم اختصار الإعدادات هذا. افتح الإعدادات يدويًا على الهاتف.\n' + result)
                else:
                    messagebox.showinfo('إعدادات الهاتف', 'تابع على شاشة الهاتف. توفر التحديثات وتأكيد العمليات يحددهما النظام والشركة المصنعة.')
            self.background(lambda: self.adb.shell(serial, 'am', 'start', '-a', action), done)

    def reset(self):
        if not self.selected():
            return
        if messagebox.askyesno('تحذير: مسح البيانات', 'إعادة ضبط المصنع تمسح التطبيقات والصور والملفات والحسابات من الهاتف.\nاحفظ نسخة احتياطية وتأكد من معرفة حساب Google لتجنب قفل FRP.\n\nهل تريد فتح صفحة إعادة الضبط على الهاتف؟ لن ينفذ التطبيق المسح. التأكيد النهائي على الهاتف.'):
            self.settings('android.settings.FACTORY_RESET')

    def save(self):
        if not self.report:
            messagebox.showinfo('التقرير', 'نفّذ الفحص أولاً.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as out:
                    json.dump(self.report, out, ensure_ascii=False, indent=2)
            except OSError as exc:
                messagebox.showerror('حفظ التقرير', str(exc))


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
