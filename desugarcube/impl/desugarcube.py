import json
import re
import sys
from argparse import ArgumentParser
from functools import lru_cache, partial
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, cast


class Support:
    _LINK_PATTERN = re.compile(r'\[\[(.*?)]]')
    _INPUT_PATTERN = re.compile(r"{text input for:.*?'(.*?)'}")

    @staticmethod
    def ensure_file(path: Union[str, Path]) -> Path:
        path = Path(path)

        if not path.is_file():
            raise IOError(f"File does not exist at: {path.absolute()}")

        return path

    @staticmethod
    def str_to_pair(str_: str, *, sep: str) -> Tuple[str, Optional[str]]:
        maybe_pair = str_.split(sep, maxsplit=1)

        if len(maybe_pair) == 2:
            return maybe_pair[0].strip(), maybe_pair[1].strip()

        return str_.strip(), None

    @staticmethod
    def str_to_list(str_: str, *, sep: Optional[str] = None) -> List[str]:
        if sep is None:
            list_ = str_.splitlines()
        else:
            list_ = str_.split(sep)

        return list(map(str.strip, list_))

    @staticmethod
    def attrs_to_dict(attrs: List[Tuple[str, Optional[str]]], *, exclude: Iterable[str] = (), as_list: Iterable[str] = ()) -> Dict[str, Union[str, List[str]]]:
        exclude, as_list = list(exclude), list(as_list)

        return {name: (value if name not in as_list else Support.str_to_list(value, sep=',')) for name, value in attrs if name not in exclude and value is not None and len(value) > 0}

    @staticmethod
    def data_to_expressions(data: str) -> List[Dict[str, str]]:
        expressions_block, _ = Support.str_to_pair(data, sep='--')
        expressions_pairs = map(partial(Support.str_to_pair, sep=':'), Support.str_to_list(expressions_block))
        expressions = [{'name': name, 'value': value} for name, value in expressions_pairs]

        for expression in expressions:
            if expression['value'] is None or len(expression['value']) == 0:
                raise IOError(f"Found unbound expression: {expression['name']}")

        return cast(List[Dict[str, str]], expressions)

    @staticmethod
    @lru_cache
    def data_to_text(data: str) -> str:
        _, text_block = Support.str_to_pair(data, sep='--')

        if text_block is not None:
            return text_block

        return ''

    @staticmethod
    def data_to_links(data: str) -> List[Dict[str, str]]:
        links_pairs = map(partial(Support.str_to_pair, sep='->'), Support._LINK_PATTERN.findall(Support.data_to_text(data)))

        return [{'name': link_or_name, 'link': (link if link is not None else link_or_name)} for link_or_name, link in links_pairs]

    @staticmethod
    def data_to_input(data: str) -> List[str]:
        return list(map(str.strip, Support._INPUT_PATTERN.findall(Support.data_to_text(data))))


class SugarcubeHtmlToJson(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self._story: Dict[str, str] = {}
        self._passages: List[Dict[str, Any]] = []
        self._passage_idx: Optional[int] = None

    def _link_to_pid(self, link: Dict[str, Any]) -> str:
        try:
            return next(cast(str, passage['pid']) for passage in self._passages if link['link'] == passage['name'])
        except StopIteration as e:
            raise IOError(f"Found unbound link: {link['link']}") from e

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self._passage_idx = None

        if tag == 'tw-storydata':
            self._story = cast(Dict[str, str], Support.attrs_to_dict(attrs))
        elif tag == 'tw-passagedata':
            self._passages.append(Support.attrs_to_dict(attrs, exclude=('position', 'size'), as_list=('tags',)))
            self._passage_idx = len(self._passages) - 1

    def handle_endtag(self, tag: str) -> None:
        self._passage_idx = None

        if tag == 'tw-storydata':
            for passage in self._passages:
                if 'links' in passage:
                    passage['links'] = [{**link, 'pid': self._link_to_pid(link)} for link in passage['links']]

    def handle_data(self, data: str) -> None:
        if self._passage_idx is not None:
            self._passages[self._passage_idx]['expressions'] = Support.data_to_expressions(data)
            self._passages[self._passage_idx]['text'] = Support.data_to_text(data)

            links = Support.data_to_links(data)

            if len(links) > 0:
                self._passages[self._passage_idx]['links'] = links

            input_ = Support.data_to_input(data)

            if len(input_) > 0:
                self._passages[self._passage_idx]['input'] = input_

    def error(self, message: str) -> None:
        raise IOError(message)

    @staticmethod
    def from_path(path: Path) -> str:
        sugarcube_html_to_json = SugarcubeHtmlToJson()

        with open(path, 'r', encoding='utf-8') as file:
            sugarcube_html_to_json.feed(file.read())

        sugarcube_html_to_json.close()

        return json.dumps({**sugarcube_html_to_json._story, 'passages': sugarcube_html_to_json._passages}, ensure_ascii=False)


def _provide_sugarcube_html_path(args: List[str]) -> str:
    args_parser = ArgumentParser()
    args_parser.add_argument('target_path', type=str)

    args_namespace = args_parser.parse_args(args)

    return cast(str, args_namespace.target_path)


def _provide_sugarcube_json_path(sugarcube_html_path: Path) -> Path:
    return sugarcube_html_path.with_suffix('.json')


def main(args: List[str]) -> None:
    sugarcube_html_path = Support.ensure_file(_provide_sugarcube_html_path(args))
    sugarcube_json = SugarcubeHtmlToJson.from_path(sugarcube_html_path)

    sugarcube_json_path = _provide_sugarcube_json_path(sugarcube_html_path)
    sugarcube_json_path.unlink(missing_ok=True)

    with open(sugarcube_json_path, 'w', encoding='utf-8') as sugarcube_json_file:
        sugarcube_json_file.write(sugarcube_json)


if __name__ == '__main__':
    main(sys.argv[1:])
