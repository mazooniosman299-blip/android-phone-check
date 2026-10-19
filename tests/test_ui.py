import sys
import unittest
import tkinter as tk
from app import App


@unittest.skipUnless(sys.platform == 'win32', 'Windows UI check')
class WindowTests(unittest.TestCase):
    def test_actions_visible_at_compact_size(self):
        root = tk.Tk()
        try:
            app = App(root)
            root.geometry('900x600')
            root.update()
            self.assertEqual(len(app.metrics), 4)
            self.assertEqual(len(app.views), 3)
            for button in app.buttons:
                self.assertTrue(button.winfo_ismapped())
                bottom = button.winfo_rooty() + button.winfo_height()
                self.assertLessEqual(bottom, root.winfo_rooty() + root.winfo_height())
            app.set_view('battery', 'test battery reading')
            self.assertIn('test battery', app.views['battery'].get('1.0', 'end'))
        finally:
            root.destroy()
