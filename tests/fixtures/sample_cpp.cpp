#include <iostream>
#include <vector>
#include <string>

namespace MyLib {

class Calculator {
public:
  int add(int a, int b) { return a + b; }
};

struct Vector {
  float x, y, z;
};

} // namespace MyLib

int main() {
  MyLib::Calculator calc;
  std::cout << calc.add(1, 2) << std::endl;
  return 0;
}
