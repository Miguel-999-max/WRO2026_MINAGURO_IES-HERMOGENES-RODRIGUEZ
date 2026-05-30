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
int ladoBusqueda = 1; // 1 = empezar a la derecha, 2 = empezar a la izquierda

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
servoDireccion.attach(9);  // 50 DCHA   90 RECTO   130 IZDA 
SERVOcam.attach(10);      // 0 DCHA   86 RECTO   172 IZDA 
servoTraccion.write(Para);
servoDireccion.write(Recto);
SERVOcam.write(86);

while (!huskylens.begin(Wire)) {   // Con el while, el programa no continua hasta que se inicie la cámara
    //Serial.println("Error al iniciar HuskyLens");
    digitalWrite(13, HIGH);
    delay(1000);}
    //Huskylens iniciado
digitalWrite(13, LOW);
delay(300);   
huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
delay(300);

while (digitalRead(12) == LOW) { //espera al pulsador de inicio mientras parpadea el led
    digitalWrite(13, HIGH);
    delay(100);
    digitalWrite(13, LOW);
    delay(100);
  }
  
 }

void scan1(){   //para ver en qué zona está

  while (true){  //lectura segura
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

void scanABIERTO(){ //aquí comprueba el sentido de giro
  while (true){
servoDireccion.write(Recto);
servoTraccion.write(105);   //atras despacito hasta ver el hueco con un sensor lateral
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

servoDireccion.write(70);  //maniobra de aproximacíon
servoTraccion.write(70);
delay(2100);
servoDireccion.write(110);
servoTraccion.write(70);
huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION); //cuenta las vueltas por las lineas naranja de las esquinas
delay(2400);



while(true) {   //empieza a seguir la pared interior a 15 cm
  servoTraccion.write(0); 
  servoDireccion.write(dir);
  distDE=hc.dist(0);
  delay(30);

  dir=(80-3*(-15+distDE)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
  dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
  servoDireccion.write(dir);

  // aquí cuenta las líneas de color naranja
  
  // si está en tiempo de espera, mira si ya pasaron los 3 segundos para desbloquear
  if (rojoBloqueado) {
    if (millis() - tiempoBloqueoRojo > 3000) { 
      rojoBloqueado = false; // al pasar la linea, vuelve a activar el sensor
    }
  }

  // si el sensor esta activo pide datos a la huskylens
  if (!rojoBloqueado && huskylens.request() && huskylens.available()) {
    HUSKYLENSResult colorSuelo = huskylens.read();
    
    if (colorSuelo.command == COMMAND_RETURN_BLOCK) {
      // si ve la linea naranja y ademas esta en la parte baja de la pantalla (cerca del coche)
      if (colorSuelo.ID == rojo && colorSuelo.yCenter > 160) { 
        contadorLineas++; // suma una esquina detectada
        tiempoBloqueoRojo = millis(); // guarda el tiempo actual
        rojoBloqueado = true; // bloquea el sensor para no repetir lecturas
        
        // parpadeo rapido del led rojo de arduino al pasar la linea
        digitalWrite(ledR, HIGH); delay(100); digitalWrite(ledR, LOW);
      }
    }
  }

  // CONTROL DE FIN DE CARRERA: si llega a 13 lineas (3 vueltas) el coche para
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

servoDireccion.write(110);//maniobra de aproximacíon
servoTraccion.write(70);
servoTraccion.write(70);
delay(3100);
servoDireccion.write(70);
servoTraccion.write(70);
huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION); //cuenta las vueltas por las lineas naranja de las esquinas
delay(2200);



while(true) {   //empieza a seguir la pared interior a 15 cm
  servoTraccion.write(0); 
  servoDireccion.write(dir);
  distIZ=hc.dist(2);
  delay(30);

  dir=(80+3*(-15+distIZ)); //15 es la distancia a la pared y *3 es el factor de coreección de la dirección
  dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
  servoDireccion.write(dir);

  // aquí cuenta las líneas de color naranja
  
  // si está en tiempo de espera, mira si ya pasaron los 3 segundos para desbloquear
  if (rojoBloqueado) {
    if (millis() - tiempoBloqueoRojo > 3000) { 
      rojoBloqueado = false; // al pasar la linea, vuelve a activar el sensor
    }
  }

  // si el sensor esta activo pide datos a la huskylens
  if (!rojoBloqueado && huskylens.request() && huskylens.available()) {
    HUSKYLENSResult colorSuelo = huskylens.read();
    
    if (colorSuelo.command == COMMAND_RETURN_BLOCK) {
      // si ve la linea naranja y ademas esta en la parte baja de la pantalla (cerca del coche)
      if (colorSuelo.ID == rojo && colorSuelo.yCenter > 160) { 
        contadorLineas++; // suma una esquina detectada
        tiempoBloqueoRojo = millis(); // guarda el tiempo actual
        rojoBloqueado = true; // bloquea el sensor para no repetir lecturas
        
        // parpadeo rapido del led rojo de arduino al pasar la linea
        digitalWrite(ledR, HIGH); delay(100); digitalWrite(ledR, LOW);
      }
    }
  }

  // CONTROL DE FIN DE CARRERA: si llega a 13 lineas (3 vueltas) el coche para
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


void scanOBSTACULOS(){  //comprueba hacia que lado está mirando

  while (true){  //lectura segura
        distDE=hc.dist(0);
        delay(60);
        distIZ=hc.dist(2);
        delay(60);
        if ((distDE>2)&&(distDE<100)&&(distIZ>2)&&(distIZ<100))
            {break;}
        }

  if (distDE > distIZ) {
      desaparcaCW();
      } //CW a derechas

  if (distDE < distIZ) {
      desaparcaCCW();
      } //CWW a izquierdas
}

 
void desaparcaCW(){ //sale del aparcamiento a derechas
  
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


void desaparcaCCW(){  //sale del aparcamiento a izquiedas
  
  //Falta probar esto
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
      
      // si encuentra un objeto valido procesa su posicion
      if (objetoEncontrado) {
        
        // hace que la camara regrese al centro despacito si se habia quedado girada
        if (anguloCam > 86) { anguloCam--; SERVOcam.write(anguloCam); delay(5); }
        if (anguloCam < 86) { anguloCam++; SERVOcam.write(anguloCam); delay(5); }

        // EL BLOQUE ESTÁ LEJOS: El robot se dirige hacia él centrándolo en el eje X
        // Cuando se acerca al bloque, el bloque aparece cada vez más abajo y la yCenter crece
        if (objetoCercano.yCenter < 130) { //con el valor yCenter controla cuanto se acerca al bloque
          
          // Con esto el robot se dirige al bloque de frente
          dir = 90 + 0.5 * (160 - objetoCercano.xCenter);
          dir = constrain(dir, Dcha, Izda); // Dcha<90 y Izda>90
          
          servoDireccion.write(dir); 
          servoTraccion.write(70); // Avanzar con tracción trasera
          
        } 
        // EL BLOQUE ESTÁ CERCA: el robot se para
        else {
          servoTraccion.write(90);      // el robot se para
          servoDireccion.write(90);     // y endereza las ruedas
          
          // Fase de decisión de color
          determinarColorYEsquivar();
        }
        
      }
    }

    // si no ve nada avanza lento velocidad 80 y mueve la camara a los lados buscando objeto
    else {
      servoDireccion.write(Recto);
      servoTraccion.write(80); // velocidad lenta requerida de busqueda

      // mueve el servo de la camara de lado a lado usando tiempo no bloqueante cada 20ms
      if (millis() - tiempoCam > 20) {
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


void determinarColorYEsquivar() {
 // cambia al modo de reconocimiento de color
  huskylens.writeAlgorithm(ALGORITHM_COLOR_RECOGNITION);
  delay(250); // esperar a quer cambie de modo
  
  // mira el color
  if (huskylens.request() && huskylens.available()) {
    
    int maxAncho = 0;
    int idColorMasCercano = 0;
    
    // Recorrem todos los bloques detectados en este frame para buscar el más grande (cercano)
    //a veces ve dos colores al mismo tiempo
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
      servoDireccion.write(90);
      delay(2500);
      servoTraccion.write(90);      // Detiene el motor de tracción
      servoDireccion.write(90);     // Enderezar las ruedas delanteras
      delay(5000);
      
      ladoBusqueda = 2; // despues de esquivar bloque rojo por la derecha busca el siguiente a la izquierda

    } 

    else if (idColorMasCercano == verde) {
      // Esquivar por la izquierda
      
      digitalWrite(ledV, HIGH); // Enciende el led verde como testigo de "Verde detectado"
      delay(2000);
      digitalWrite(ledV, LOW);
      servoDireccion.write(Izda); // Izda 130
      servoTraccion.write(80); 
      delay(1000);
      servoDireccion.write(90);
      delay(2500);
      servoTraccion.write(90);      // Detener el motor de tracción de inmediato
      servoDireccion.write(90);     // Enderezar las ruedas delanteras
      delay(5000);
      
      ladoBusqueda = 1; // despues de esquivar bloque verde por la izquierda busca el siguiente a la derecha

    }
  }
  
  // cambia de nuevo a tracking y detiene el coche para mirar fijamente antes de arrancar
  huskylens.writeAlgorithm(ALGORITHM_OBJECT_TRACKING);
  servoTraccion.write(Para); // se detiene a mirar por completo
  servoDireccion.write(Recto);
  delay(1000); // tiempo muerto de seguridad parado mirando antes de reanudar el bucle


}



void loop() {
  scan1(); // arranca el escaneo de salida para elegir el desafio
}
