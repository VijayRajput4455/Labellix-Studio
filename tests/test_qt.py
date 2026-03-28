
from unittest import TestCase
from unittest import skipUnless


def _can_import_app():
    try:
        import PyQt5  # noqa: F401
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


if _can_import_app():
    from PyQt5.QtGui import QImage
    from labellix_studio import get_main_app


@skipUnless(_can_import_app(), 'PyQt5 and lxml are required for Qt tests')
class TestMainWindow(TestCase):

    app = None
    win = None

    def setUp(self):
        self.app, self.win = get_main_app()

    def tearDown(self):
        self.win.close()
        self.app.quit()

    def test_noop(self):
        pass

    def test_paint_canvas_with_null_image_no_crash(self):
        self.win.image = QImage()
        self.win.paint_canvas()
