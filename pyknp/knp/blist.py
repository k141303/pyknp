#-*- encoding: utf-8 -*-

from pyknp import Argument, Pas
from pyknp import Bunsetsu
from pyknp import Morpheme
from pyknp import Tag
from pyknp import TList
from pyknp import SynNodes, SynNode
from pyknp import DrawTree
import re
import sys
import unittest
import json
import bisect


class BList(DrawTree):
    """
    文節列を保持するオブジェクト．
    """

    def __init__(self, spec='', pattern='EOS'):
        self._bnst = []
        self._readonly = False
        self.pattern = pattern
        self.comment = ''
        self.sid = ''
        self._pinfos = []
        self.parse(spec)
        self.set_parent_child()
        self.set_positions()
        self._setPAS()

    def _setPAS(self):
        """Set PAS to BList with new format"""
        for pinfo in self._pinfos:
            pinfo = json.loads(pinfo)
            start = pinfo[u"head_token_start"]
            end = pinfo[u"head_token_end"]
            tag_idx = bisect.bisect(self.tag_positions, end) - 1
            tag = self.tag_list()[tag_idx]
            tag.features.pas = Pas()
            tag.features.pas.cfid = pinfo[u"cfid"]

            for casename, argsinfo in pinfo[u"args"].items():
                #                 possible_cases = argsinfo[u"possible_cases"]
                for arg in argsinfo[u"arguments"]:
                    arg_tag_idx = bisect.bisect(self.tag_positions, arg[u"head_token_end"]) - 1
                    arg_sid = None
                    if arg[u"sid"] is None:
                        arg_sid = self.sid
                    else:
                        arg_sid = arg[u"sid"]
                    arg = Argument(arg_sid, arg_tag_idx, arg[u"rep"])
                    tag.features.pas.arguments[casename].append(arg)

    def parse(self, spec):
        newstyle = False
        for string in spec.split('\n'):
            if string.strip() == "":
                continue
            if string.startswith(u'#\t') and newstyle:
                items = string.split(u"\t")
                if len(items) >= 3 and items[1] == u"PAS":
                    self._pinfos.append(items[2])
            elif string.startswith('#'):
                newstyle = False
                self.comment = string
                match = re.match(r'# S-ID:(.*?)[ $]', self.comment)
                if match:
                    self.sid = match.group(1)
                if 'KNP++' in string:
                    newstyle = True
            elif re.match(self.pattern, string):
                break
            elif string.startswith(';;'):
                sys.stderr.write("Error: %s\n" % string)
                quit(1)
            elif string.startswith('*'):
                bnst = Bunsetsu(string, len(self._bnst))
                self._bnst.append(bnst)
            elif string.startswith('+'):
                if newstyle:
                    bnst = Bunsetsu(string, len(self._bnst), newstyle)
                    self._bnst.append(bnst)
                self._bnst[-1].push_tag(
                    Tag(string, len(self.tag_list()), newstyle))
            elif string.startswith('!!'):
                synnodes = SynNodes(string)
                self._bnst[-1].tag_list().push_synnodes(synnodes)
            elif string.startswith('!') and not string.startswith('! ! !'):
                synnode = SynNode(string)
                self._bnst[-1].tag_list().push_synnode(synnode)
            elif string.startswith('EOS'):
                pass
            else:
                mrph = Morpheme(string, len(self.mrph_list()), newstyle)
                self._bnst[-1].push_mrph(mrph)

    def set_positions(self):
        self.mrph_positions = [0]
        self.tag_positions = [0]
        for mrph in self.mrph_list():
            self.mrph_positions.append(self.mrph_positions[-1] + len(mrph.midasi))
        for tag in self.tag_list():
            start_mrph_id = tag.mrph_list()[0].mrph_id
            end_mrph_id = tag.mrph_list()[-1].mrph_id
            length = self.mrph_positions[end_mrph_id + 1] - self.mrph_positions[start_mrph_id]
            self.tag_positions.append(self.tag_positions[-1] + length)

    def get_tag_span(self, tag_id):
        return (self.tag_positions[tag_id], self.tag_positions[tag_id + 1] - 1)

    def set_parent_child(self):
        for bnst in self._bnst:
            if bnst.parent_id == -1:
                bnst.parent = None
            else:
                bnst.parent = self._bnst[bnst.parent_id]
                self._bnst[bnst.parent_id].children.append(bnst)
            for tag in bnst._tag_list:
                if tag.parent_id == -1:
                    tag.parent = None
                else:
                    tag.parent = self.tag_list()[tag.parent_id]
                    self.tag_list()[tag.parent_id].children.append(tag)

    def push_bnst(self, bnst):
        self._bnst.append(bnst)
        self._bnst[bnst.parent].child.append(bnst.bnst_id)

    def tag_list(self):
        result = []
        for bnst in self._bnst:
            for tag in bnst.tag_list():
                result.append(tag)
        return result

    def mrph_list(self):
        result = []
        for bnst in self._bnst:
            for mrph in bnst.mrph_list():
                result.append(mrph)
        return result

    def bnst_list(self):
        return self._bnst

    def set_readonly(self):
        for bnst in self._bnst:
            bnst.set_readonly()
        self._readonly = True

    def spec(self):
        return "%s\n%s%s\n" % (self.comment, ''.join(b.spec() for b in self._bnst), self.pattern)

    def all(self):
        return self.spec()

    def __getitem__(self, index):
        return self._bnst[index]

    def __len__(self):
        return len(self._bnst)

    def draw_bnst_tree(self, fh=None):
        """ 文節列の依存関係を木構造として表現して出力する． """
        self.draw_tree(fh=fh)

    def draw_tag_tree(self, fh=None):
        """ タグ列の依存関係を木構造として表現して出力する． """
        tlist = TList()
        for tag in self.tag_list():
            tlist.push_tag(tag)
        tlist.draw_tree(fh=fh)

    def draw_tree_leaves(self):
        """ draw_tree メソッドとの通信用のメソッド． """
        return self.bnst_list()

    def get_clause_starts(self):
        def levelOK(lv):
            if lv.startswith(u"B") or lv.startswith(u"C") or lv == u"A":
                return True
            return False

        starts = [0]
        paren_level = 0
        tags = self.tag_list()
        for idx, tag in enumerate(tags):
            features = tag.features  # alias

            if features.get(u"括弧始"):
                paren_level += 1
            elif features.get(u"括弧終"):
                paren_level -= 1
            level = features.get(u"レベル")

            if (paren_level == 0) and (level is not None) and levelOK(level):
                kakari = features.get(u"係")
                myid = features.get(u"ID")
                if kakari in [u"連格", u"連体"]:
                    continue
                elif (features.get(u"格要素") or features.get(u"連体修飾")) and (features.get(u"補文") or level == u"A"):
                    continue
                elif myid in [u"〜と（いう）", u"〜と（引用）", u"〜と（する）", u"〜のように", u"〜とは", u"〜くらい〜", u"〜の〜", u"〜ように", u"〜く", u"〜に", u"（副詞的名詞）"]:
                    continue
                elif features.get(u"〜によれば"):
                    continue

                if idx != len(tags) - 1:
                    starts.append(idx + 1)
        return starts


class BListTest(unittest.TestCase):

    def setUp(self):
        self.result = u"# S-ID:123 KNP:4.2-ffabecc DATE:2015/04/10 SCORE:-18.02647\n" \
            u"* 1D <BGH:解析/かいせき><文頭><サ変><助詞><連体修飾><体言>\n" \
            u"+ 1D <BGH:構文/こうぶん><文節内><係:文節内><文頭><体言>\n" \
            u"構文 こうぶん 構文 名詞 6 普通名詞 1 * 0 * 0 \"代表表記:構文/こうぶん カテゴリ:抽象物\" <代表表記:構文/こうぶん>\n" \
            u"+ 2D <BGH:解析/かいせき><助詞><連体修飾><体言>\n" \
            u"解析 かいせき 解析 名詞 6 サ変名詞 2 * 0 * 0 \"代表表記:解析/かいせき カテゴリ:抽象物 ドメイン:教育・学習;科学・技術\" <代表表記:解析/かいせき>\n" \
            u"の の の 助詞 9 接続助詞 3 * 0 * 0 NIL <かな漢字><ひらがな><付属>\n" \
            u"* 2D <BGH:実例/じつれい><ヲ><助詞><体言><係:ヲ格>\n" \
            u"+ 3D <BGH:実例/じつれい><ヲ><助詞><体言><係:ヲ格>\n" \
            u"実例 じつれい 実例 名詞 6 普通名詞 1 * 0 * 0 \"代表表記:実例/じつれい カテゴリ:抽象物\" <代表表記:実例/じつれい>\n" \
            u"を を を 助詞 9 格助詞 1 * 0 * 0 NIL <かな漢字><ひらがな><付属>\n" \
            u"* -1D <BGH:示す/しめす><文末><句点><用言:動>\n" \
            u"+ -1D <BGH:示す/しめす><文末><句点><用言:動>\n" \
            u"示す しめす 示す 動詞 2 * 0 子音動詞サ行 5 基本形 2 \"代表表記:示す/しめす\" <代表表記:示す/しめす><正規化代表表記:示す/しめす>\n" \
            u"。 。 。 特殊 1 句点 1 * 0 * 0 NIL <英記号><記号><文末><付属>\n" \
            u"EOS"

    def test(self):
        blist = BList(self.result)
        self.assertEqual(len(blist), 3)
        self.assertEqual(len(blist.tag_list()), 4)
        self.assertEqual(len(blist.mrph_list()), 7)
        self.assertEqual(''.join([mrph.midasi for mrph in blist.mrph_list()]),
                         u'構文解析の実例を示す。')
        self.assertEqual(blist.sid, '123')
        # Check parent/children relations
        self.assertEqual(blist[1].parent, blist[2])
        self.assertEqual(blist[1].parent_id, 2)
        self.assertEqual(blist[2].parent, None)
        self.assertEqual(blist[2].parent_id, -1)
        self.assertEqual(blist[1].children, [blist[0]])
        self.assertEqual(blist[0].children, [])
        self.assertEqual(blist.tag_list()[1].parent, blist.tag_list()[2])
        self.assertEqual(blist.tag_list()[2].children, [blist.tag_list()[1]])
        self.assertEqual(blist.mrph_positions, [0, 2, 4, 5, 7, 8, 10, 11])
        self.assertEqual(blist.tag_positions, [0, 2, 5, 8, 11])
        spans = [(0, 1), (2, 4), (5, 7), (8, 10)]
        for i, t in enumerate(blist.tag_list()):
            self.assertEqual(blist.get_tag_span(t.tag_id), spans[i])


class BList2Test(unittest.TestCase):

    def setUp(self):
        self.result = u"""# S-ID:none KNP++:a9af601
+	0	3	D	1;3	母が	母/ぼ	-	-	-	-	-	-	-	-	-	-	BP:Phrase|CFG_RULE_ID:1|BOS|BP_TYPE|ガ|助詞
-	1	0	0	0	母	母/ぼ	ぼ	母	名詞	6	普通名詞	1	*	0	*	0	漢字読み:音|漢字|CONT|RelWord-105522
-	3	1;2	1	1	が	*	が	が	助詞	9	接続助詞	3	*	0	*	0	FUNC|Ｔ固有付属|Ｔ固有任意
+	1	3	D	5;6	姉に	姉/あね	-	-	-	-	-	-	-	-	-	-	BP:Phrase|CFG_RULE_ID:1|BP_TYPE|ニ|助詞|体言
-	5	3;4	2	2	姉	姉/あね	あね	姉	名詞	6	普通名詞	1	*	0	*	0	漢字読み:訓|カテゴリ:人|漢字|CONT|LD
-	6	5	3	3	に	*	に	に	助詞	9	接続助詞	3	*	0	*	0	FUNC|Ｔ固有付属|Ｔ固有任意
+	2	3	D	8;9	弁当を	弁当/べんとう	-	-	-	-	-	-	-	-	-	-	BP:Phrase|CFG_RULE_ID:1|BP_TYPE|ヲ
-	8	6;7	4	5	弁当	弁当/べんとう	べんとう	弁当	名詞	6	普通名詞	1	*	0	*	0	カテゴリ:人工物-食べ
-	9	8	6	6	を	*	を	を	助詞	9	格助詞	1	*	0	*	0	FUNC|Ｔ固有付属|Ｔ固有任意
+	3	-1	D	10	渡した	渡す/わたす	-	-	-	-	-	-	-	-	-	-	EOS|BP:Phrase|CFG_RULE_ID:0|BP_TYPE
-	10	9	7	9	渡した	渡す/わたす	わたした	渡す	動詞	2	*	0	子音動詞サ行	5	タ形	10	付属動詞候補（基本）
#	PAS	{"predtype" : "PRED", "sid":null, "token_start":7, "token_end":9, "rep":"渡す/わたす", "head_token_start":7, "head_token_end":9, "cfid" : "渡す/わたす:動1", "score" : -27.2318, "args" : {"ヲ" : {"possible_cases": ["ヲ"], "arguments": [{"sid":null, "token_start":4, "token_end":6, "rep":"弁当/べんとう", "head_token_start":4, "head_token_end":6}]}, "ガ" : {"possible_cases": ["ガ"], "arguments": [{"sid":null, "token_start":0, "token_end":1, "rep":"母/ぼ", "head_token_start":0, "head_token_end":1}]}, "ニ" : {"possible_cases": ["ニ"], "arguments": [{"sid":null, "token_start":2, "token_end":3, "rep":"姉/あね", "head_token_start":2, "head_token_end":3}]}}}
EOS"""

    def test(self):
        blist = BList(self.result)
        self.assertEqual(len(blist), 4)
        self.assertEqual(len(blist.tag_list()), 4)
        self.assertEqual(len(blist.mrph_list()), 7)
        self.assertEqual(''.join([mrph.midasi for mrph in blist.mrph_list()]),
                         u'母が姉に弁当を渡した')
        self.assertEqual(blist.sid, 'none')
        self.assertEqual(blist[1].parent, blist[3])
        self.assertEqual(blist[1].parent_id, 3)
        self.assertEqual(blist[3].parent, None)
        self.assertEqual(blist[3].parent_id, -1)
        self.assertEqual(blist[0].children, [])
        self.assertEqual(blist[1].children, [])
        self.assertEqual(blist[3].children, [blist[0], blist[1], blist[2]])

        self.assertEqual(blist.tag_list()[1].parent, blist.tag_list()[3])
        self.assertEqual(blist.tag_list()[3].children, [blist.tag_list()[0], blist.tag_list()[1], blist.tag_list()[2]])
        self.assertEqual(blist.mrph_positions, [0, 1, 2, 3, 4, 6, 7, 10])
        self.assertEqual(blist.tag_positions, [0, 2, 4, 7, 10])
        spans = [(0, 1), (2, 3), (4, 6), (7, 9)]
        for i, t in enumerate(blist.tag_list()):
            self.assertEqual(blist.get_tag_span(t.tag_id), spans[i])
        self.assertEqual(blist.get_clause_starts(), [0])

if __name__ == '__main__':
    unittest.main()
