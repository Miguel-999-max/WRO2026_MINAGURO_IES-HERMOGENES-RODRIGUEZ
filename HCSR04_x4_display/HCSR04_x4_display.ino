#include <HCSR04.h>

HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)
int lectura=0;
int distDE, distFR, distIZ, distTR;

#include <LiquidCrystal_I2C.h>
LiquidCrystal_I2C lcd(0x27,20,4);

void setup()
{ 
  lcd.init(); //inicializa el display
  lcd.backlight(); //Activa la retroiluminación
  lcd.clear();
 
 }

void loop()
{
  lcd.clear();
  
  lcd.setCursor(0, 0);// coloca el cursor en la columna 0, linea 0
  lcd.print("Dist Dcha= ");
  lectura=(int)hc.dist(0);
  if (lectura < 2 || lectura > 300) {
  distDE = distDE; }
  else{distDE=lectura;}
  lcd.print(distDE);
  delay(60);

  lcd.setCursor(0, 1);// coloca el cursor en la columna 0, linea 0
  lcd.print("Dist Fron= ");
  lectura=(int)hc.dist(1);
  if (lectura < 2 || lectura > 300) {
  distFR = distFR; }
  else{distFR=lectura;}
  lcd.print(distFR);
  delay(60);

  lcd.setCursor(0, 2);// coloca el cursor en la columna 0, linea 0
  lcd.print("Dist Izda= ");
  lectura=(int)hc.dist(2);
  if (lectura < 2 || lectura > 300) {
  distIZ = distIZ; }
  else{distIZ=lectura;}
  lcd.print(distIZ);
  delay(60);

  lcd.setCursor(0, 3);// coloca el cursor en la columna 0, linea 0
  lcd.print("Dist Tras= ");
  lectura=(int)hc.dist(3);
  if (lectura < 2 || lectura > 300) {
  distTR = distTR; }
  else{distTR=lectura;}
  lcd.print(distTR);
  delay(60);

delay(400);
}