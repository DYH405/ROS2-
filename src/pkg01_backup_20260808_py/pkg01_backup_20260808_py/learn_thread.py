import threading
import requests

class Download:
    def download(self,url,callback_world_count): # erl：网址
        print(f'thread_{threading.get_ident()} start download:{url}')
        response = requests.get(url)
        response.encoding = 'utf-8'
        callback_world_count(url,response.text)

    def start_download(self,url,callback_world_count):
        thread = threading.Thread(target=self.download,args=(url,callback_world_count))
        thread.start() # 启动线程

def world_count(url,result):
    """
    普通函数,用于回调
    """
    print(f'{url},单词数：{len(result)}->{result[0:5]}')

def main():
    download = Download()
    download.start_download('http://0.0.0.0:8000/novel1.txt',world_count)
    download.start_download('http://0.0.0.0:8000/novel2.txt',world_count)
    download.start_download('http://0.0.0.0:8000/novel3.txt',world_count)


    


