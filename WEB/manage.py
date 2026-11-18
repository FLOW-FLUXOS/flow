#!/usr/bin/env python
"""FLOW Web — front-end. Só entrega as telas; os dados vêm das APIs pelo navegador."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
