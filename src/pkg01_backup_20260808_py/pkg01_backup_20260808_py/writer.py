from pkg01_backup_20260808_py.person_node import PersonNode

class writerNode(PersonNode):
    def __init__(
            self,
            name:str,
            book:str,
            age:int
            ) ->None:
        print("writerNode")
        super().__init__(name, age)
        self.book = book

    def read(self,book_name:str):
        print(f'{self.name},{self.age}在读{book_name}')

def main():
    node = writerNode("鱼想ROS", "快速入狱", 18 )
    node.eat('鱼想ROS')
    node.read("快速入狱")
        