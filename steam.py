import sys
import requests
import json
import re
import pandas as pd
from datetime import datetime
from io import StringIO
import os
import argparse


class SteamFriends:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('-w', '--web_api', type=str, help='Web API value')
        self.parser.add_argument('-i', '--id', type=str, help='Steam ID')
        self.parser.add_argument('-p', '--proxy', type=str, help='Proxy')

        # 解析参数
        self.args = self.parser.parse_args()

        # 获取参数值
        self.steam_web_api = self.args.web_api or os.environ.get('web_api')
        self.steam_id = self.args.id or os.environ.get('id')

        self.friends = 0        # 总数
        self.friend_ids = []    # 向steam请求的id列表（url）
        self.friends_list = {}  # 查询到的所有好友，以及：好友日期

        self.steamid = []       # 点击立即跳转到对应界面（Markdown格式）
        self.steamid_num = []   # 记录一份只有id的列表
        self.bfd = []           # 成为好友的日期
        self.name = []          # steam资料名
        self.profileurl = []    # 暂时没用
        self.avatar = []        # 头像（Markdown格式）

        self.friend_list_url = 'https://api.steampowered.com/ISteamUser/GetFriendList/v0001/'
        self.friend_summaries_url = 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/'
        self.sess = requests.Session()
        if self.args.proxy is not None:
            self.sess.proxies.update({
                'http': self.args.proxy,
                'https': self.args.proxy,
            })
        self.sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537'
                                                '.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'})

    def GetFriendList(self):
        params = {
            'key': self.steam_web_api,
            'steamid': self.steam_id,
        }
        response = self.sess.get(self.friend_list_url, params=params)
        if response.status_code == 200:
            print('success')
        elif response.status_code == 401:
            print('Unauthorized，请检查你的steam隐私设置，如果设置为仅限好友和私密将无法获取好友列表')
            sys.exit(401)
        elif response.status_code == 403:
            print('403Forbidden，请检查你的web_api和id的值，别复制了空格')
            sys.exit(403)
        else:
            print(f'收到未处理的状态码：{response.status_code}')
        json_list = json.loads(response.text)
        self.friends_list = {friend['steamid']: friend['friend_since'] for friend in json_list['friendslist']['friends']}
        self.friends = len(self.friends_list)

    def GetFriendsSummaries(self):
        for num, id in enumerate(self.friends_list):
            self.friend_ids.append(id)
            if (num + 1) % 100 == 0:
                self.GetFriendsStatus()
                self.friend_ids = []
        self.GetFriendsStatus()

    def GetFriendsStatus(self):
        if not self.friend_ids:
            return False
        steam_ids = ''
        for id in self.friend_ids:
            steam_ids = steam_ids + id + ','
        steam_ids = steam_ids[:-1]
        params = {
            'key': self.steam_web_api,
            'steamids': steam_ids,
        }
        response = self.sess.get(self.friend_summaries_url, params=params)
        json_list = json.loads(response.text)
        users_list = json_list['response']['players']
        for user in users_list:
            self.steamid_num.append(user['steamid'])
            self.steamid.append('[' + user['steamid'] + '](https://steamcommunity.com/profiles/' + user['steamid'] + '/)')
            name = user['personaname']
            name = re.sub(r'[|\-+:\\\"\'\n\r]', '`', name)  # 防止名字中有特殊符号影响程序和渲染
            self.name.append(name)
            self.avatar.append('![](' + user['avatar'] + ')')

    def CreateFrom(self):
        with open('./README.md', 'r', encoding='utf-8') as file:
            original_content = file.read()
        is_friend = ['✅' for _ in self.avatar]
        empty_list = ['' for _ in self.avatar]
        for steamid in self.steamid_num:
            bfd_unix = self.friends_list[steamid]
            self.bfd.append(datetime.utcfromtimestamp(bfd_unix).strftime('%Y-%m-%d %H:%M:%S'))
        data = {
            'Avatar': self.avatar,
            'Name': self.name,
            'steamid': self.steamid,
            'is_friend': is_friend,
            'BFD': self.bfd,
            'removed_time': empty_list,
            'Remark': empty_list
        }
        df = pd.DataFrame(data)
        markdown_table = df.to_markdown(index=False)
        updated_content = f"{original_content}\n\n## Steam好友列表\n\n{markdown_table}"
        with open('./README.md', 'w', encoding='utf-8') as file:
            file.write(updated_content)

    def Update(self):
        with open('./README.md', 'r', encoding='utf-8') as file:
            content = file.readlines()

        # 找到 Markdown 表格的开始位置
        table_start_index = None
        for i, line in enumerate(content):
            if line.strip().startswith('|'):
                table_start_index = i
                break

        # 提取表格内容
        table_content = ''.join(content[table_start_index:])

        # 转换 Markdown 表格为 pandas DataFrame
        # 去掉表头的分隔线
        table_content = '\n'.join(line for line in table_content.strip().split('\n') if not line.startswith('|:'))

        table_content = re.sub(r'[\"\']', '', table_content)    # 临时补牢，最终解决办法见上面名字替换字符

        # 使用 tabulate 解析表格内容
        try:
            df = pd.read_csv(StringIO(table_content), sep='|', engine='python', skipinitialspace=True)
            df.columns = [col.strip() for col in df.columns]  # 去掉列名的多余空格
            df = df.apply(lambda x: x.map(lambda y: y.strip() if isinstance(y, str) else y))  # 去除每一个值里面多余的空格
            df = df.iloc[:, 1:-1]  # 去掉第一列和最后一列的空白列
            df = df.fillna('')  # 删除所有NaN单元格
        except Exception as e:
            print("Error:", e)
            df = pd.DataFrame()  # 处理错误时返回空 DataFrame

        # 重新判断好友
        friend_array = []
        if 'removed_time' not in df.columns:  # 适配旧版本
            df['removed_time'] = ''

        for num, sid in enumerate(self.steamid):
            if df[df['steamid'] == sid].empty:
                # print("没有找到匹配的 ID")
                new_friend = {
                    'Avatar': self.avatar[num],
                    'Name': self.name[num],
                    'steamid': self.steamid[num],
                    'is_friend': '✅',
                    'BFD': datetime.utcfromtimestamp(self.friends_list[self.steamid_num[num]]).strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    'removed_time': '',
                    'Remark': ''
                }
                df.loc[len(df)] = new_friend
                friend_array.append(sid)
            else:
                df.loc[df['steamid'] == sid, 'is_friend'] = '✅'
                df.loc[df['steamid'] == sid, 'Avatar'] = self.avatar[num]
                df.loc[df['steamid'] == sid, 'Name'] = self.name[num]
                df.loc[df['steamid'] == sid, 'removed_time'] = ''
                friend_array.append(sid)
        # update complete
        # find removed friend

        for steamid in df['steamid']:
            if steamid not in friend_array:
                # this friend has been removed
                df.loc[df['steamid'] == steamid, 'is_friend'] = '❌'
                if df.loc[df['steamid'] == steamid, 'removed_time'].iloc[0] == '':
                    df.loc[df['steamid'] == steamid, 'removed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        df = df.fillna('')
        df = df.sort_values(by='removed_time', ascending=False)

        updated_markdown_table = df.to_markdown(index=False)
        updated_content = ''.join(content[:table_start_index]) + updated_markdown_table
        with open('./README.md', 'w', encoding='utf-8') as file:
            file.write(updated_content)

    def UpdateOrCreate(self):
        with open('./README.md', 'r', encoding='utf-8') as file:
            original_content = file.read()
        if '|' in original_content:
            self.Update()
        else:
            self.CreateFrom()

    def GetData(self):
        self.GetFriendList()
        self.GetFriendsSummaries()
        self.UpdateOrCreate()


if __name__ == '__main__':
    app = SteamFriends()
    app.GetData()
