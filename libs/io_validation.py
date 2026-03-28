import os


def ensure_required_path(path_value, error_cls, message):
    if not path_value:
        raise error_cls(message)


def ensure_directory(path_value, error_cls, missing_message):
    if not os.path.isdir(path_value):
        raise error_cls(missing_message)


def ensure_distinct_directories(source_dir, output_dir, error_cls, message):
    source_root = os.path.realpath(source_dir)
    output_root = os.path.realpath(output_dir)
    if source_root == output_root:
        raise error_cls(message)
    return source_root, output_root


def ensure_output_is_directory_or_create(output_dir, error_cls, not_directory_message):
    if os.path.exists(output_dir) and not os.path.isdir(output_dir):
        raise error_cls(not_directory_message)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)


def ensure_new_output_directory(output_dir, error_cls, exists_message,
                                parent_missing_message, parent_not_writable_message):
    if os.path.exists(output_dir):
        raise error_cls(exists_message)

    output_parent = os.path.dirname(output_dir) or '.'
    if not os.path.isdir(output_parent):
        raise error_cls(parent_missing_message)
    if not os.access(output_parent, os.W_OK):
        raise error_cls(parent_not_writable_message)


def ensure_relative_path(path_value, error_cls, message):
    if os.path.isabs(path_value):
        raise error_cls(message)


def ensure_path_within_root(path_value, root_dir, error_cls, message):
    path_real = os.path.realpath(path_value)
    root_real = os.path.realpath(root_dir)
    if not path_real.startswith(root_real + os.path.sep) and path_real != root_real:
        raise error_cls(message)
    return path_real