"""仓库树上的引用闭环：每个技能载荷内的相对链接必须在载荷内解析。

双技能拆分后参考资料在 research/ 与 drafting/ 之间移动过；链接断掉不影响任何
Python 行为，只有专门检查才抓得到。为什么「必须在载荷内」：安装用户拿到的是
单个技能目录，仓库里能靠 `../` 解析的跨技能链接在安装后是死链——跨技能导航
一律走文内的技能交接说明（见各 SKILL.md），不用文件链接。
打包后的版本（解包 zip）在 test_release.py 里用同一工具复检。
"""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("link_checker", ROOT / "tools/check_reference_links.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReferenceLinkClosure(unittest.TestCase):
    def test_repo_tree_links_resolve_inside_each_payload(self):
        problems = checker.check(ROOT)
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
