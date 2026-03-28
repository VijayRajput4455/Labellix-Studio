import os
import sys
import unittest


def _has_qt_bindings():
    try:
        import PyQt5  # noqa: F401
        return True
    except ImportError:
        try:
            import PyQt4  # noqa: F401
            return True
        except ImportError:
            return False


if _has_qt_bindings():
    from libs.utils import Struct, new_action, new_icon, add_actions, format_shortcut, generate_color_by_text, natural_sort, set_icon_preferences, get_icon_preferences

@unittest.skipUnless(_has_qt_bindings(), 'PyQt5 or PyQt4 is required for utils tests')
class TestUtils(unittest.TestCase):

    def test_generateColorByGivingUniceText_noError(self):
        res = generate_color_by_text(u'\u958B\u555F\u76EE\u9304')
        self.assertTrue(res.green() >= 0)
        self.assertTrue(res.red() >= 0)
        self.assertTrue(res.blue() >= 0)

    def test_nautalSort_noError(self):
        l1 = ['f1', 'f11', 'f3']
        expected_l1 = ['f1', 'f3', 'f11']
        natural_sort(l1)
        for idx, val in enumerate(l1):
            self.assertTrue(val == expected_l1[idx])

    def test_icon_preferences_accessors(self):
        set_icon_preferences(use_modern_svg=False, use_native=True, use_theme=False, tint_color='#112233')
        prefs = get_icon_preferences()
        self.assertEqual(prefs.get('use_modern_svg_icons'), False)
        self.assertEqual(prefs.get('use_native_icons'), True)
        self.assertEqual(prefs.get('use_theme_icons'), False)
        self.assertEqual(prefs.get('icon_tint_color'), '#112233')

        # Restore default preferences for other tests.
        set_icon_preferences(use_modern_svg=True, use_native=True, use_theme=True, tint_color=None)

if __name__ == '__main__':
    unittest.main()
