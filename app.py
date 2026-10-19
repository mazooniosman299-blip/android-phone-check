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
        root.title('فاحص أندرويد | لوحة الجهاز')
        width = min(1120, root.winfo_screenwidth() - 80)
        height = min(760, root.winfo_screenheight() - 100)
        root.geometry(f'{width}x{height}')
        root.minsize(760, 520)
        root.configure(bg='#0d1424')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 11), background='#0d1424', foreground='#e7edf7')
        style.configure('TFrame', background='#0d1424')
        style.configure('TLabel', background='#0d1424', foreground='#e7edf7')
        style.configure('TButton', background='#24344e', foreground='#ffffff', borderwidth=0, padding=(14, 10))
        style.map('TButton', background=[('active', '#355076'), ('disabled', '#192235')], foreground=[('disabled', '#7e8da4')])
        style.configure('Primary.TButton', background='#246bea')
        style.map('Primary.TButton', background=[('active', '#4386ff'), ('disabled', '#24344e')])
        style.configure('Danger.TButton', foreground='#ffb2b9', background='#422536')
        style.configure('TCombobox', fieldbackground='#19263c', foreground='#ffffff', arrowcolor='#a6b8d4', padding=8)
        style.map('TCombobox', fieldbackground=[('readonly', '#19263c')], foreground=[('readonly', '#ffffff')])
        style.configure('TNotebook', background='#0d1424', borderwidth=0)
        style.configure('TNotebook.Tab', background='#19263c', foreground='#aebed5', padding=(18, 9))
        style.map('TNotebook.Tab', background=[('selected', '#246bea')], foreground=[('selected', '#ffffff')])
        self.buttons = []
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        header = ttk.Frame(root, padding=(22, 16))
        header.grid(row=0, column=0, sticky='ew')
        ttk.Label(header, text='ANDROID / USB', foreground='#6aa5ff', font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Label(header, text='لوحة فحص الهاتف', font=('Segoe UI', 24, 'bold')).pack(side='right')
        connection = ttk.Frame(root, padding=(22, 0, 22, 12))
        connection.grid(row=1, column=0, sticky='ew')
        self.button(connection, 'بدء الفحص', self.scan, 'Primary.TButton')
        self.button(connection, 'تحديث الأجهزة', self.refresh)
        self.selector = ttk.Combobox(connection, state='readonly', width=25)
        self.selector.pack(side='right', padx=8)
        self.status = tk.StringVar(value='بانتظار توصيل الهاتف')
        ttk.Label(connection, textvariable=self.status, foreground='#8da5c6').pack(side='left')
        cards = ttk.Frame(root, padding=(22, 0, 22, 12))
        cards.grid(row=2, column=0, sticky='ew')
        self.metrics = {}
        for index, (key, title, unit) in enumerate([
            ('storage', 'التخزين المستخدم', 'نسبة استخدام مساحة البيانات'),
            ('memory', 'الذاكرة المتاحة', 'RAM المتاحة الآن'),
            ('temperature', 'حرارة البطارية', 'درجة مئوية'),
            ('battery', 'شحن البطارية', 'قراءة النظام الحالية')]):
            cards.columnconfigure(index, weight=1, uniform='cards')
            card = tk.Frame(cards, bg='#19263c', padx=14, pady=12, highlightthickness=1, highlightbackground='#293b56')
            card.grid(row=0, column=index, sticky='nsew', padx=(0 if index == 0 else 8, 0))
            tk.Label(card, text=title, bg='#19263c', fg='#a9bad4', font=('Segoe UI', 11)).pack(anchor='e')
            value = tk.StringVar(value='—')
            self.metrics[key] = value
            tk.Label(card, textvariable=value, bg='#19263c', fg='#79b3ff', font=('Segoe UI', 24, 'bold')).pack(anchor='e', pady=4)
            tk.Label(card, text=unit, bg='#19263c', fg='#7e93b2', font=('Segoe UI', 9)).pack(anchor='e')
        notebook = ttk.Notebook(root)
        notebook.grid(row=3, column=0, sticky='nsew', padx=22)
        self.views = {}
        for key, title in [('overview', 'نظرة عامة'), ('battery', 'البطارية'), ('performance', 'الأداء والتخزين')]:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            text = tk.Text(frame, wrap='word', font=('Segoe UI', 12), padx=18, pady=16,
                           bg='#131e30', fg='#dbe6f8', insertbackground='#ffffff',
                           relief='flat', borderwidth=0, height=7, highlightthickness=0)
            scroll = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
            scroll.pack(side='left', fill='y')
            text.configure(yscrollcommand=scroll.set)
            text.pack(fill='both', expand=True)
            text.tag_configure('rtl', justify='right', spacing1=4, spacing3=6)
            text.configure(state='disabled')
            self.views[key] = text
        self.output = self.views['overview']
        actions = ttk.Frame(root, padding=(22, 12))
        actions.grid(row=4, column=0, sticky='ew')
        self.button(actions, 'حفظ التقرير', self.save)
        self.button(actions, 'تحديث النظام', lambda: self.settings('android.settings.SYSTEM_UPDATE_SETTINGS'))
        self.button(actions, 'إعادة ضبط المصنع…', self.reset, 'Danger.TButton')
        ttk.Label(root, text='معالجة محلية  •  لا مسح تلقائي  •  الفحص لا يستبعد جميع الأعطال',
                  foreground='#7e93b2', anchor='e', padding=(22, 0, 22, 12)).grid(row=5, column=0, sticky='ew')
        self.write('ابدأ بتوصيل هاتفك\n\n١. وصّل الهاتف بكابل USB يدعم نقل البيانات.\n٢. فعّل تصحيح USB من خيارات المطور.\n٣. وافق على بصمة الكمبيوتر في شاشة الهاتف.\n٤. اضغط تحديث الأجهزة، ثم اختر الهاتف وابدأ الفحص.\n\nستظهر القراءات الفعلية في البطاقات بعد الفحص. لا يلزم روت.')
        self.set_view('battery', 'لم يتم إجراء فحص بعد.\nتعرض هذه الصفحة قراءات البطارية التي يوفرها نظام الهاتف؛ نسبة الشحن ليست قياسًا للسعة الفعلية المتبقية.')
        self.set_view('performance', 'لم يتم إجراء فحص بعد.\nتظهر هنا عينة استخدام المعالج والذاكرة والتخزين. هذه القراءات ليست اختبار أداء معياريًا.')

    def button(self, parent, text, command, style='TButton'):
        button = ttk.Button(parent, text=text, command=command, style=style)
        button.pack(side='right', padx=4)
        self.buttons.append(button)

    def set_view(self, key, content):
        view = self.views[key]
        view.configure(state='normal')
        view.delete('1.0', 'end')
        view.insert('end', content, 'rtl')
        view.configure(state='disabled')

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
            import re
            try:
                scale = int(battery.get('scale', '100'))
                level = int(battery['level'])
                self.metrics['battery'].set(f'{round(level / scale * 100)}%' if scale > 0 else '—')
            except (KeyError, ValueError):
                self.metrics['battery'].set('—')
            self.metrics['temperature'].set(temperature)
            available = re.search(r'MemAvailable:\s+(\d+)', report['memory'])
            self.metrics['memory'].set(f'{int(available[1]) / 1048576:.1f} GB' if available else '—')
            used = re.findall(r'(\d+)%', report['storage'])
            self.metrics['storage'].set(used[-1] + '%' if used else '—')
            self.set_view('battery', f"الشحن: {self.metrics['battery'].get()}\nالحرارة: {temperature}\nالحالة حسب النظام: {health}\n\nهذه الحالة لا تقيس السعة الفعلية أو دورات الشحن.\n\nقراءات النظام:\n" + '\n'.join(f'{key}: {value}' for key, value in battery.items()))
            self.set_view('performance', 'التخزين:\n' + report['storage'] + '\n\nالذاكرة (kB):\n' + '\n'.join(report['memory'].splitlines()[:6]) + '\n\nاستخدام المعالج والعمليات:\n' + report['cpu'])
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
