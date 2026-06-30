import json
import re
import time
import requests
from pathlib import Path

class LuoguScraper:
    """GET LUOGU PROBLEM(防风控模式) -- BY PERKICA"""
    
    def __init__(self, cookie):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self.session.cookies.update({
            '__client_id': cookie
        })
    
    def fetch_problem(self, pid):
        """爬取单个题目"""
        url = "https://www.luogu.com.cn/problem/" + pid
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            pattern = r'<script\s+id="lentille-context"\s+type="application/json">(.*?)</script>'
            match = re.search(pattern, response.text, re.DOTALL)
            
            if not match:
                print("    未找到题目数据，可能需要登录或题号不存在")
                return None
            
            raw_json = match.group(1)
            data = json.loads(raw_json)
            
            problem = data.get('currentData', {}).get('problem', {})
            if not problem:
                problem = data.get('data', {}).get('problem', {})
            
            if not problem:
                print("    解析数据失败")
                return None
            
            content = problem.get('content') or problem.get('contenu') or {}
            
            title = problem.get('title', '')
            if not title:
                title = content.get('name', '')
            if not title:
                title = problem.get('pid', '')
            
            result = {
                'pid': problem.get('pid', ''),
                'title': title,
                'difficulty': problem.get('difficulty', 0),
                'background': content.get('background', ''),
                'description': content.get('description', ''),
                'inputFormat': content.get('formatI', content.get('inputFormat', '')),
                'outputFormat': content.get('formatO', content.get('outputFormat', '')),
                'hint': content.get('hint', ''),
                'samples': [],
                'limits': {},
                'tags': problem.get('tags', []),
                'totalSubmit': problem.get('totalSubmit', 0),
                'totalAccepted': problem.get('totalAccepted', 0),
            }
            
            for s in problem.get('samples', []):
                if len(s) >= 2:
                    input_text = s[0]
                    output_text = s[1]
                    if isinstance(input_text, str):
                        input_text = input_text.strip()
                    if isinstance(output_text, str):
                        output_text = output_text.strip()
                    result['samples'].append({
                        'input': input_text,
                        'output': output_text
                    })
            
            limits = problem.get('limits', {})
            if limits:
                time_limits = limits.get('time', [1000])
                memory_limits = limits.get('memory', [262144])
                result['limits'] = {
                    'time': time_limits[0] if time_limits else 1000,
                    'memory': memory_limits[0] if memory_limits else 262144
                }
            else:
                result['limits'] = {
                    'time': 1000,
                    'memory': 262144
                }
            
            return result
            
        except requests.RequestException as e:
            print("    网络错误: " + str(e))
            return None
        except json.JSONDecodeError as e:
            print("    JSON解析错误: " + str(e))
            return None
        except Exception as e:
            print("    未知错误: " + str(e))
            return None
    
    def _cdata(self, text):
        """创建CDATA标记的文本"""
        if text is None:
            text = ''
        return '<![CDATA[' + str(text) + ']]>'
    
    def generate_item_xml(self, problem):
        """生成单个题目的item XML"""
        lines = []
        lines.append('    <item>')
        
        title = problem['title'] if problem['title'] else problem['pid']
        lines.append('        <title>' + self._cdata(title) + '</title>')
        lines.append('        <url>' + self._cdata('') + '</url>')
        
        time_s = max(1, problem['limits'].get('time', 1000) // 1000)
        lines.append('        <time_limit unit="s">' + self._cdata(str(time_s)) + '</time_limit>')
        
        memory_mb = max(1, problem['limits'].get('memory', 262144) // 1024)
        lines.append('        <memory_limit unit="mb">' + self._cdata(str(memory_mb)) + '</memory_limit>')
        
        desc_text = ''
        if problem['background']:
            desc_text += problem['background'] + '\n\n'
        desc_text += problem['description']
        lines.append('        <description>' + self._cdata(desc_text) + '</description>')
        
        lines.append('        <input>' + self._cdata(problem['inputFormat']) + '</input>')
        lines.append('        <output>' + self._cdata(problem['outputFormat']) + '</output>')
        
        if problem['samples']:
            sample_inputs = []
            sample_outputs = []
            for sample in problem['samples']:
                sample_inputs.append(sample['input'])
                sample_outputs.append(sample['output'])
            
            lines.append('        <sample_input>' + self._cdata('\n'.join(sample_inputs)) + '</sample_input>')
            lines.append('        <sample_output>' + self._cdata('\n'.join(sample_outputs)) + '</sample_output>')
            
            for i, sample in enumerate(problem['samples']):
                test_name = 'test' + str(i)
                lines.append('        <test_input name="' + test_name + '">' + self._cdata(sample['input']) + '</test_input>')
                lines.append('        <test_output name="' + test_name + '">' + self._cdata(sample['output']) + '</test_output>')
        else:
            lines.append('        <sample_input>' + self._cdata('') + '</sample_input>')
            lines.append('        <sample_output>' + self._cdata('') + '</sample_output>')
        
        lines.append('        <hint>' + self._cdata(problem.get('hint', '')) + '</hint>')
        
        source_text = problem['title'] if problem['title'] else problem['pid']
        lines.append('        <source>' + self._cdata(source_text) + '</source>')
        lines.append('        <remote_oj>' + self._cdata('') + '</remote_oj>')
        lines.append('        <remote_id>' + self._cdata('') + '</remote_id>')
        
        lines.append('    </item>')
        return '\n'.join(lines)
    
    def generate_fps_xml(self, problems):
        """生成完整的fps XML文件，包含多个item"""
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        xml_lines.append('<fps version="1.5" url="https://github.com/zhblue/freeproblemset/">')
        xml_lines.append('<generator name="HUSTOJ" url="https://github.com/zhblue/hustoj/"/>')
        
        for problem in problems:
            item_xml = self.generate_item_xml(problem)
            xml_lines.append(item_xml)
        
        xml_lines.append('</fps>')
        return '\n'.join(xml_lines)
    
    def save_merged_xml(self, problems, filename='merged_problems.xml', output_dir='hustoj_problems'):
        """保存多个题目合并的XML文件"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        xml_content = self.generate_fps_xml(problems)
        filepath = output_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        return filepath


def parse_pid_range(start_pid, end_pid):
    """解析题号范围，生成题号列表"""
    match_start = re.match(r'([A-Za-z]+)(\d+)', start_pid)
    match_end = re.match(r'([A-Za-z]+)(\d+)', end_pid)
    
    if not match_start or not match_end:
        return None
    
    prefix_start, num_start = match_start.groups()
    prefix_end, num_end = match_end.groups()
    
    if prefix_start.upper() != prefix_end.upper():
        return None
    
    num_start = int(num_start)
    num_end = int(num_end)
    
    if num_start > num_end:
        num_start, num_end = num_end, num_start
    
    prefix = prefix_start.upper()
    return [prefix + str(i) for i in range(num_start, num_end + 1)]


def main():
    print("=" * 60)
    print("    洛谷题目爬取器 - HUSTOJ XML导出工具")
    print("=" * 60)
    print()
    
    print("请在浏览器中登录 luogu.com.cn")
    print("F12 -> Application -> Cookies -> __client_id")
    print()
    cookie = input("请输入 __client_id: ").strip()
    
    if not cookie:
        print("Cookie不能为空，程序退出")
        return
    
    print("\nCookie已设置: " + cookie[:20] + "...")
    print()
    
    scraper = LuoguScraper(cookie)
    
    while True:
        print("\n" + "=" * 60)
        print("请选择模式:")
        print("  1. 单题目爬取")
        print("  2. 多题目范围爬取 (如: P1001-P1004)")
        print("  q. 退出程序")
        print("=" * 60)
        
        choice = input("\n请输入选择 (1/2/q): ").strip()
        
        if choice.lower() == 'q':
            print("\n再见！")
            break
        
        elif choice == '1':
            pid = input("请输入题号 (如 P1001): ").strip()
            if not pid:
                continue
            
            print("\n正在爬取 " + pid + " ...")
            problem = scraper.fetch_problem(pid)
            
            if problem:
                filename = pid + ".xml"
                filepath = scraper.save_merged_xml([problem], filename=filename)
                print("\n✓ 成功保存到: " + str(filepath))
                print("题目信息:")
                print("  标题: " + problem['title'])
                print("  难度: " + str(problem['difficulty']))
                print("  时间限制: " + str(problem['limits'].get('time', 1000)) + "ms")
                print("  内存限制: " + str(problem['limits'].get('memory', 262144)) + "KB")
                print("  样例数量: " + str(len(problem['samples'])))
            else:
                print("\n✗ 爬取失败")
            
            time.sleep(0.2)
        
        elif choice == '2':
            range_input = input("请输入题号范围 (如 P1001-P1004): ").strip()
            
            if '-' not in range_input:
                print("格式错误，请使用如 P1001-P1004 的格式")
                continue
            
            parts = range_input.split('-')
            if len(parts) != 2:
                print("格式错误")
                continue
            
            start_pid, end_pid = parts[0].strip(), parts[1].strip()
            pid_list = parse_pid_range(start_pid, end_pid)
            
            if not pid_list:
                print("题号范围解析失败，请检查格式")
                continue
            
            print("\n将爬取以下 " + str(len(pid_list)) + " 个题目: " + ', '.join(pid_list))
            confirm = input("确认开始? (y/n): ").strip()
            
            if confirm.lower() != 'y':
                continue
            
            success_problems = []
            failed_pids = []
            
            for i, pid in enumerate(pid_list, 1):
                print("\n[" + str(i) + "/" + str(len(pid_list)) + "] 正在爬取 " + pid + " ...")
                problem = scraper.fetch_problem(pid)
                
                if problem:
                    print("  ✓ 标题: " + problem['title'])
                    success_problems.append(problem)
                else:
                    print("  ✗ 爬取失败")
                    failed_pids.append(pid)
                
                time.sleep(0.2)
            
            # 合并导出成一个XML文件
            if success_problems:
                filename = start_pid + "_" + end_pid + "_merged.xml"
                filepath = scraper.save_merged_xml(success_problems, filename=filename)
                print("\n✓ 合并导出成功!")
                print("  文件: " + str(filepath))
                print("  包含题目: " + str(len(success_problems)) + " 个")
            
            print("\n爬取统计:")
            print("  成功: " + str(len(success_problems)) + " 个")
            print("  失败: " + str(len(failed_pids)) + " 个")
            if failed_pids:
                print("  失败的题号: " + ', '.join(failed_pids))
        
        else:
            print("无效选择，请重新输入")


if __name__ == '__main__':
    main()
