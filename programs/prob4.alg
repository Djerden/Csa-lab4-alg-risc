val max_pal = 0;
val a = 999;
val b;
val product;
val reversed;
val original;
val digit;
val temp;

while(a >= 100) {
  b = a;
  while(b >= 100) {
    product = a * b;
    if(product > max_pal) {
      original = product;
      reversed = 0;
      temp = original;
      while(temp > 0) {
        digit = temp % 10;
        reversed = reversed * 10 + digit;
        temp = temp / 10;
      }
      if(reversed == original) {
        max_pal = product;
      }
    }
    b = b - 1;
  }
  a = a - 1;
}

put max_pal;