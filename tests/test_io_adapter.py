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
    from libs.io_adapter import AnnotationIORegistry
    from libs.labelFile import LabelFileFormat


@unittest.skipUnless(_has_qt_bindings(), 'PyQt5 or PyQt4 is required for io adapter tests')
class TestAnnotationIORegistry(unittest.TestCase):

    def test_ensure_extension_for_all_formats(self):
        registry = AnnotationIORegistry()

        voc = registry.get_by_format(LabelFileFormat.PASCAL_VOC)
        yolo = registry.get_by_format(LabelFileFormat.YOLO)
        create_ml = registry.get_by_format(LabelFileFormat.CREATE_ML)

        self.assertEqual(voc.ensure_extension('/tmp/sample'), '/tmp/sample.xml')
        self.assertEqual(voc.ensure_extension('/tmp/sample.xml'), '/tmp/sample.xml')

        self.assertEqual(yolo.ensure_extension('/tmp/sample'), '/tmp/sample.txt')
        self.assertEqual(yolo.ensure_extension('/tmp/sample.txt'), '/tmp/sample.txt')

        self.assertEqual(create_ml.ensure_extension('/tmp/sample'), '/tmp/sample.json')
        self.assertEqual(create_ml.ensure_extension('/tmp/sample.json'), '/tmp/sample.json')


if __name__ == '__main__':
    unittest.main()
