# -*- coding: utf-8 -*-
import json
import csv
import random
from constants.env import FILE_ENCODING, RESULTS_PATH
from common.errors import FileError, JSONError


class FileManager:
    @staticmethod
    def fetch_loaded_csv_files(path):
        results = []
        try:
            for file_path in path.iterdir():
                if file_path.is_file() and ".csv" in file_path.name:
                    if line_count := FileManager.fetch_line_count(file_path) - 1:
                        results.append({
                            "fileName": file_path.name,
                            "lineCount": line_count
                        })
        except (FileNotFoundError, PermissionError):
            return []

        return results

    @staticmethod
    def fetch_loaded_dirs(path):
        results = []
        try:
            for dir_path in path.iterdir():
                if dir_path.is_dir() and dir_path.name != RESULTS_PATH.name:
                    if loaded_files := FileManager.fetch_loaded_csv_files(dir_path):
                        results.append({
                            "dirName": dir_path.name,
                            "fileCount": len(loaded_files),
                            "files": loaded_files
                        })
        except (FileNotFoundError, PermissionError):
            return []

        return results

    @staticmethod
    def fetch_line_count(file_path):
        try:
            with open(file_path, "r+b") as file:
                line_count = sum(
                    buf.count(b"\n") for buf in iter(
                        lambda: file.read(2 ** 16), b""
                    )
                ) + 1

                if line_count > 1:
                    file.seek(-1, 2)
                    if file.read(1) == b"\n":
                        line_count -= 1

                return line_count
        except (FileNotFoundError, PermissionError):
            return 0

    @staticmethod
    def fetch_json_file(file_path):
        try:
            with open(file_path, encoding=FILE_ENCODING) as file:
                return {
                    key: (
                        value.strip() if isinstance(value, str) else {
                            key: value.strip() if isinstance(value, str) else value
                            for key, value in value.items()
                        } if isinstance(value, dict) else value
                    ) for key, value in json.load(file).items()
                }
        except FileNotFoundError:
            raise FileError(file_path.name, "not found")
        except PermissionError:
            raise FileError(file_path.name, "unopenable")
        except JSONError:
            raise FileError(file_path.name, "malformed")

    @staticmethod
    def fetch_csv_files(path, files):
        results = []
        for file_name in files:
            try:
                with open(path / file_name, encoding=FILE_ENCODING) as file:
                    results += [
                        line for line in csv.DictReader(file)
                        if None not in line and None not in line.values()
                        and list(filter(None, line.values()))
                    ]
            except (FileNotFoundError, PermissionError):
                continue

        random.shuffle(results)
        return results
