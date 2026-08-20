#include <HUSKYLENS.h>  //Cable verde al A4  y   cable azul al A5
#include <Wire.h>
HUSKYLENS huskylens;
const int rojo = 1;
const int verde = 2;

#include <HCSR04.h>
HCSR04 hc(2, new int[4]{3, 4, 5, 7}, 4); //initialisation class HCSR04 (trig pin , echo pin, number of sensor)

#include <Servo.h>
Servo servoTraccion;
Servo servoDireccion;
Servo SERVOcam;

#define ledV 14
#define ledR 15

int i=0;
int dir=90;     
int distDE=15;  // SENSOR 0 derecho
int distFR=110; // SENSOR 1 frontal
int distIZ=15;  // SENSOR 2 izquierdo
int distTR=15;  // SENSOR 3 trasero

// Variables control servos
int Izda=134;
int Dcha=54;
int Recto=94;
int Para=90;
int Avanza=0;
int Retrocede=180;
int lectura=0;
int CASO;

//variable para esquivar obstáculos.
int anguloCam = 86;           // guarda la posicion actual del servo de la camara
int direccionBarrido = 5;     // velocidad y sentido del barrido (positivo derecha, negativo izquierda)
unsigned long tiempoCam = 0;  // controla el refresco del movimiento del servo de la camara

//variables para contar vueltas en el desafío libre.
int contadorLineas = 0;              // guarda las lineas rojas que va cruzando
unsigned long tiempoBloqueoRojo = 0; // guarda el momento exacto en que pisa el rojo
bool rojoBloqueado = false;          // bandera para saber si esta en el tiempo de espera

void setup()
{ //Serial.begin(9600);
Wire.begin(); // Iniciar el bus I2C
pinMode (12, INPUT);
pinMode (13, OUTPUT);
pinMode(ledV, OUTPUT); //led verde
pinMode(ledR, OUTPUT);  //led rojo

servoTraccion.attach(6);  // 0 AVANZA   90 STOP    180 RETROCEDE
servoDireccion.attach(9);  // 54 DCHA   94 RECTO   134 IZDA 
SERVOcam.attach(10);      // 0 DCHA   86 RECTO   172 IZDA 
servoTraccion.write(Para);
servoDireccion.write(Recto);
SERVOcam.write(86);

while (!huskylens.begin(Wire)) {   // Con el while, el programa no continua hasta que se inicie la cámara
    //Serial.println("Error al iniciar HuskyLens");
    digitalWrite(13, HIGH);
    delay(1000);}
    digitalWrite(13, LOW);
delay(300);   
huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
delay(300);

while (digitalRead(12) == LOW) {
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void scan1(){
  while (true){
distFR=hc.dist(1);
delay(60);
if ((distFR>2)&&(distFR<250))
    {break;}
}

if (distFR > 40) {
      digitalWrite(ledV, HIGH); 
      delay(2000);
      digitalWrite(ledV, LOW);
   CASO=1;  //El robot esta en la zona de salida
   scanABIERTO();
   } 

if (distFR < 40) {
      digitalWrite(ledR, HIGH); 
      delay(2000);
      digitalWrite(ledR, LOW);
   CASO=2;   //El robot esta en el aparcamiento
   scanOBSTACULOS();
   } 
}

////////////////////zona Desafio Abierto////////////////////////////////

void scanABIERTO(){
  while (true){
servoDireccion.write(Recto);
servoTraccion.write(105); //atras despacito hasta ver el hueco con un sensor lateral
distDE=hc.dist(0);
delay(30);
distIZ=hc.dist(2);
delay(30);
if ((distDE>90)||(distIZ>90)) //detecta hueco a un lado
    { delay(30);
      servoTraccion.write(Para);
      break;}
}

if (distDE < distIZ) {
   giroCCW();
   } //CCW a izquierdas

if (distDE > distIZ) {
   giroCW();
   } //CW a derechas
}

void giroCW(){

servoDireccion.write(70);
servoTraccion.write(70);
delay(2100);
servoDireccion.write(110);
servoTraccion.write(70);
huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION);
delay(2400);



while(true) {
  servoTraccion.write(0); 
  servoDireccion.write(dir);
  distDE=hc.dist(0);
  delay(30);

  dir=(80-3*(-15+distDE)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
  dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
  servoDireccion.write(dir);

  // LOGICA PARA CONTAR LAS LINEAS ROJAS DEL SUELO
  
  // si estamos en tiempo de espera miramos si ya pasaron los 3 segundos para desbloquear
  if (rojoBloqueado) {
    if (millis() - tiempoBloqueoRojo > 3000) { 
      rojoBloqueado = false; // ya pasamos la linea, volvemos a activar el sensor
    }
  }

  // si el sensor esta activo pedimos datos a la huskylens
  if (!rojoBloqueado && huskylens.request() && huskylens.available()) {
    HUSKYLENSResult colorSuelo = huskylens.read();
    
    if (colorSuelo.command == COMMAND_RETURN_BLOCK) {
      // si ve la linea roja y ademas esta en la parte baja de la pantalla (cerca del coche)
      if (colorSuelo.ID == rojo && colorSuelo.yCenter > 160) { 
        contadorLineas++; // sumamos una esquina detectada
        tiempoBloqueoRojo = millis(); // guardamos el tiempo actual
        rojoBloqueado = true; // bloqueamos el sensor para no repetir lecturas
        
        // testigo visual: parpadeo rapido del led rojo de arduino al pasar la linea
        digitalWrite(ledR, HIGH); delay(100); digitalWrite(ledR, LOW);
      }
    }
  }

  // CONTROL DE FIN DE CARRERA: si llegamos a 12 lineas (3 vueltas) el coche para
  if (contadorLineas >= 13) {
    servoTraccion.write(Para); // detiene el motor
    servoDireccion.write(Recto); // endereza ruedas
    while(true) {
      // bucle infinito de parada final de carrera
      digitalWrite(ledR, HIGH); digitalWrite(ledV, HIGH); // leds fijos de fin de carrera
    }
  }
}
}


void giroCCW(){

servoDireccion.write(110);
servoTraccion.write(70);
delay(3100);
servoDireccion.write(70);
servoTraccion.write(70);
huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION);
delay(2200);



while(true) {
  servoTraccion.write(0); 
  servoDireccion.write(dir);
  distIZ=hc.dist(2);
  delay(30);

  dir=(80+3*(-15+distIZ)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
  dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
  servoDireccion.write(dir);

  // LOGICA PARA CONTAR LAS LINEAS ROJAS DEL SUELO
  
  // si estamos en tiempo de espera miramos si ya pasaron los 3 segundos para desbloquear
  if (rojoBloqueado) {
    if (millis() - tiempoBloqueoRojo > 3000) { 
      rojoBloqueado = false; // ya pasamos la linea, volvemos a activar el sensor
    }
  }

  // si el sensor esta activo pedimos datos a la huskylens
  if (!rojoBloqueado && huskylens.request() && huskylens.available()) {
    HUSKYLENSResult colorSuelo = huskylens.read();
    
    if (colorSuelo.command == COMMAND_RETURN_BLOCK) {
      // si ve la linea roja y ademas esta en la parte baja de la pantalla (cerca del coche)
      if (colorSuelo.ID == rojo && colorSuelo.yCenter > 160) { 
        contadorLineas++; // sumamos una esquina detectada
        tiempoBloqueoRojo = millis(); // guardamos el tiempo actual
        rojoBloqueado = true; // bloqueamos el sensor para no repetir lecturas
        
        // testigo visual: parpadeo rapido del led rojo de arduino al pasar la linea
        digitalWrite(ledR, HIGH); delay(100); digitalWrite(ledR, LOW);
      }
    }
  }

  // CONTROL DE FIN DE CARRERA: si llegamos a 12 lineas (3 vueltas) el coche para
  if (contadorLineas >= 13) {
    servoTraccion.write(Para); // detiene el motor
    servoDireccion.write(Recto); // endereza ruedas
    while(true) {
      // bucle infinito de parada final de carrera
      digitalWrite(ledR, HIGH); digitalWrite(ledV, HIGH); // leds fijos de fin de carrera
    }
  }
}

}



////////////////////zona Desafio de Obstaculos////////////////////////////////


void scanOBSTACULOS(){
  while (true){
distDE=hc.dist(0);
delay(60);
distIZ=hc.dist(2);
delay(60);
if ((distDE>2)&&(distDE<100)&&(distIZ>2)&&(distIZ<100))
    {break;}
}

if (distDE > distIZ) {
   desaparcaCW();
   } //CW a izquierdas

if (distDE < distIZ) {
   desaparcaCCW();
   } //CWW a derechas
}

 
void desaparcaCW(){
  
 distTR = hc.dist(3);

  delay(50);
    
    if (distTR > 5) {

          servoTraccion.write(100);
    }
    
    else {

          servoTraccion.write(Para);
          delay(500);
          servoDireccion.write(Dcha);
          servoTraccion.write(80);
          delay(2800);

          servoTraccion.write(Para);
          delay(2000);



giroObstCW();
      }
}

void giroObstCW(){  //este programa vale para los dos sentidos de giro, creo

  while(true) {
    // solicita datos a la huskylens en modo object tracking
    if (huskylens.request() && huskylens.available()) {
      
      HUSKYLENSResult objetoCercano;
      int maxAnchoObjeto = 0;
      bool objetoEncontrado = false;

      // filtra en tiempo real todos los bloques para quedarse solo con el mas ancho que es el mas cercano
      while (huskylens.available()) {
        HUSKYLENSResult objetoActual = huskylens.read();
        
        if (objetoActual.command == COMMAND_RETURN_BLOCK) {
          if (objetoActual.width > maxAnchoObjeto) {
            maxAnchoObjeto = objetoActual.width;
            objetoCercano = objetoActual;
            objetoEncontrado = true;
          }
        }
      }
      
      // si encuentra un objeto valido saltamos al nuevo subprograma de seguimiento
      if (objetoEncontrado) {
        centrarYPerseguir(objetoCercano);
      }
    }

    // si no ve nada se detiene a escanear girando la camara a los lados buscando objeto
    else {
      servoDireccion.write(Recto);
      servoTraccion.write(Para); // modificado para que escanee completamente parado

      // mueve el servo de la camara de lado a lado usando tiempo no bloqueante cada 50ms
      if (millis() - tiempoCam > 50) {
        tiempoCam = millis();
        anguloCam += direccionBarrido;

        // limites mecanicos del barrido de la camara de un lado a otro (0 a 172 grados)
        if (anguloCam >= 172 || anguloCam <= 0) {
          direccionBarrido = -direccionBarrido; // invierte el sentido al llegar al tope
        }
        SERVOcam.write(anguloCam);
      }
    }
  }
}


void centrarYPerseguir(HUSKYLENSResult objeto) {
  // controlamos el refresco de los servos a 50ms para que sea fluido y no de tirones
  if (millis() - tiempoCam > 50) {
    tiempoCam = millis();

    bool objetoCentradoEnPantalla = false;

    // 1. CORRECCION DEL CUELLO: el servo del husky se mueve para centrar el objeto en su pantalla
    // si el objeto esta a la derecha (xCenter > 180) movemos el servo hacia la derecha, si esta a la izquierda al reves
    if (objeto.xCenter > 180) {
      anguloCam -= 1; // modificado a paso de 1 grado para maxima precision
    } else if (objeto.xCenter < 140) {
      anguloCam += 1; // modificado a paso de 1 grado para maxima precision
    } else {
      objetoCentradoEnPantalla = true; // el objeto ya esta en la zona central del monitor
    }
    
    anguloCam = constrain(anguloCam, 0, 172); // seguridad para el servo de la camara
    SERVOcam.write(anguloCam);

    // 2. DECISION DE MOVIMIENTO: si la camara ya centro el objeto en su monitor, el coche avanza
    if (objetoCentradoEnPantalla) {
      
      // si la camara ya esta fija con el objeto el coche avanza y se guia con la estrategia que conocemos
      if (objeto.yCenter < 130) {
        
        // correccion dinamica combinada: apunta las ruedas hacia donde esta mirando el cuello de la camara
        // si la camara mira a la izquierda (anguloCam > 86), dir sera mayor de 90 y el coche girara a la izquierda
        dir = 90 + (anguloCam - 86) * 0.6; 
        dir = constrain(dir, Dcha, Izda);
        
        servoDireccion.write(dir);
        servoTraccion.write(70); // avanza lento hacia el bloque ya coordinado
        
      } else {
        // el bloque esta muy cerca y el robot se para
        servoTraccion.write(90);      
        servoDireccion.write(90);     
        determinarColorYEsquivar(); // fase de decision de color
      }
      
    } else {
      // 3. ENCARAR PARADO: si el objeto entro en el mapa pero la camara aun lo esta centrando
      // el coche se queda quieto pero ya va orientando las ruedas hacia el angulo de la camara
      servoTraccion.write(Para); 
      
      if (anguloCam > 86) {
        servoDireccion.write(Izda - 15); // tuerce las ruedas hacia la izquierda para ir encarando
      } else {
        servoDireccion.write(Dcha + 15); // tuerce las ruedas hacia la derecha
      }
    }
  }
}




void determinarColorYEsquivar() {
 // cambia al modo de reconocimiento de color
  huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION);
  delay(250); // esperar a quer cambie de modo
  
  // miramos el color
  if (huskylens.request() && huskylens.available()) {
    
    int maxAncho = 0;
    int idColorMasCercano = 0;
    
    // Recorremos todos los bloques detectados en este frame para buscar el más grande (cercano)
    while (huskylens.available()) {
      HUSKYLENSResult bloqueActual = huskylens.read();
      
      if (bloqueActual.command == COMMAND_RETURN_BLOCK) {
        if (bloqueActual.width > maxAncho) {
          maxAncho = bloqueActual.width;
          idColorMasCercano = bloqueActual.ID;
        }
      }
    }
    
    if (idColorMasCercano == rojo) {
      
      //Esquivar por la derecha
      digitalWrite(ledR, HIGH); // Enciende el led rojo como testigo de "Rojo detectado"
      delay(2000);
      digitalWrite(ledR, LOW);
      servoDireccion.write(Dcha); // Dcha 50
      servoTraccion.write(80); 
      delay(1000);
      servoDireccion.write(Recto);
      delay(2500);
      servoTraccion.write(90);      // Detener el motor de tracción de inmediato
      servoDireccion.write(90);     // Enderezar las ruedas delanteras
      delay(5000);
      
     
    } 

    else if (idColorMasCercano == verde) {
      // Esquivar por la izquierda
      
      digitalWrite(ledV, HIGH); // Enciende el led verde como testigo de "Verde detectado"
      delay(2000);
      digitalWrite(ledV, LOW);
      servoDireccion.write(Izda); // Izda 130
      servoTraccion.write(80); 
      delay(1000);
      servoDireccion.write(Recto);
      delay(2500);
      servoTraccion.write(90);      // Detener el motor de tracción de inmediato
      servoDireccion.write(Recto);     // Enderezar las ruedas delanteras
      delay(5000);
      
  
    }
}

huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
delay(300);

giroObstCW();
}

void desaparcaCCW(){
  distTR = hc.dist(3);
  delay(50);
  
  if (distTR > 3) {
    servoTraccion.write(100);
  }
  else {
    servoTraccion.write(Para);
    delay(500);
    servoDireccion.write(Izda);
    servoTraccion.write(80);
    delay(2800);
    servoTraccion.write(Para);
    delay(50000);
    
    // aqui iria la llamada a giroObstCCW si lo necesitas luego
  }
}

void loop() {
scan1();
}

