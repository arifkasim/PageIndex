import functools

def my_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("Something is happening before the function is called.")
        func(*args, **kwargs)
        print("Something is happening after the function is called.")
    return wrapper

@my_decorator
def say_whee():
    """Docstring for say_whee."""
    print("Whee!")

class Dog:
    """A class representing a dog."""
    
    def __init__(self, name):
        self.name = name

    def bark(self):
        return "Woof!"

async def async_hello(name: str) -> str:
    return f"Hello, {name}"
