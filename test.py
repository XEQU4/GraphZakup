def is_palindrom(word: str) -> bool:
    if not word:
        raise ValueError('Вы ввели пустое слово!')
    
    word_mid = len(word) // 2
    
    for index in range(len(word)):
        letter = word[index]
        last_letter = word[-(index + 1)]
        
        if letter != last_letter:
            return False
        
        if index == word_mid:
            return True
        

def duplicates(my_list: list, delete: bool = True) -> dict | list:
    my_dict = {}
    
    for item in my_list:
        if item not in my_dict:
            my_dict[item] = 1
        else:
            my_dict[item] += 1
    
    if delete:
        return list(my_dict.keys())
    return my_dict


def fizzbuzz():
    for item in range(1, 101):
        if item % 3 == 0 and item % 5 != 0:
            print('Fizz')
        elif item % 5 == 0 and item % 3 != 0:
            print('Buzz')
        elif item % 5 == 0 and item % 3 == 0:
            print('FizzBuzz')
        else:
            print(item)
            
        
def pass_hash(password: str) -> str:
    import hashlib
    
    return hashlib.sha256(password.encode()).hexdigest()
        
        
if __name__ == '__main__':
    # print(is_palindrom(''))
    # print(duplicates([1, 2, 2, 3, 4, 2, 5, 6], delete=False))
    # print(fizzbuzz())
    print(pass_hash('qwerty'))