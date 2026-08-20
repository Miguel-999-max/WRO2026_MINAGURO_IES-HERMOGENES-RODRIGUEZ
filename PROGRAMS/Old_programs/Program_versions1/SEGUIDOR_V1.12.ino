// 
#include <Wire.h>
#include <LSM303.h>// 0x1E: Es el Magnetómetro (brújula) del LSM303DLHC.
                    //0x19: Es el Acelerómetro del LSM303DLHC.
                    //0x69: Es el Giroscopio (probablemente un L3GD20 o similar, que suele acompañar al LSM303 en los módulos 10 DOF).
LSM303 compass;



#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo servoTraccion;
Servo servoDireccion;
Servo SERVOcam;
int i=0;
int dir=80;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero
int Izda=120;
int Dcha=60;
int Recto=87;
int Para=90;
int Avanza=0;
int Retrocede=180;


void setup()
{ Serial.begin(9600);
Wire.begin();
compass.init();
compass.enableDefault();
  compass.m_min = (LSM303::vector<int16_t>){-32767, -32767, -32767};
  compass.m_max = (LSM303::vector<int16_t>){+32767, +32767, +32767};

pinMode (12, INPUT);
pinMode (13, OUTPUT);


servoTraccion.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
servoDireccion.attach(9);  // 52 DCHA   87 RECTO   122 IZDA 
SERVOcam.attach(10);      // 0 DCHA   90 RECTO   180 IZDA 
servoTraccion.write(Para);
servoDireccion.write(Recto);
SERVOcam.write(90);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void desaparcaIzda(){
distTR = hc.dist(3);
  delay(50);
    
    if (distTR > 6) {
        servoTraccion.write(Retrocede);
    }
    else {
          servoTraccion.write(Para);
          delay(1000);}

if (distTR < 7) {
        girar90Izquierda();
    }
}

void girar90Izquierda() {

  compass.read();
  float rumboAntesDeGirar = compass.heading();
  if (rumboAntesDeGirar < 0) rumboAntesDeGirar += 360;

  float rumboDeseado = rumboAntesDeGirar - 90;
  if (rumboDeseado < 0) rumboDeseado += 360; 

  float error = 90; 

  while (abs(error) > 3) { 
    compass.read();
    float actual = compass.heading();
    if (actual < 0) actual += 360;

    error = rumboDeseado - actual;
    
    if (error > 180) error -= 360;
    if (error < -180) error += 360;

    servoDireccion.write(Izda); 
    servoTraccion.write(80); 
  }

  servoDireccion.write(Recto);
  servoTraccion.write(Para); 
}


void giroCCW(){
 servoTraccion.write(0); 
   servoDireccion.write(dir);

distIZ=hc.dist(2);// SENSOR 2 izquierdo
delay(30);
distFR=hc.dist(1);// SENSOR 1 frontal
delay(30);

if (distFR>20)
{
dir=(80+3*(-15+distIZ)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
}

else {
  while (distIZ>15)
    {dir=60;
    servoDireccion.write(dir);
    distFR=hc.dist(2);// SENSOR 2 izquierdo
    delay(30);}
    }

dir = constrain(dir, 60, 100);// 40 DCHA   80 RECTO   120 IZDA 

servoDireccion.write(dir);// 40 DCHA   80 RECTO   120 IZDA 
/*
Serial.print("dist=");
Serial.print(distIZ);
Serial.print("    dir=");
Serial.println(dir);*/
}



void loop()
{
  desaparcaIzda();

}