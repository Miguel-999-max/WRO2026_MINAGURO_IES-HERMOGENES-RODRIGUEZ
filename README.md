
# WRO Future Engineers - MINAGURO
<p align="center"><img src="MINAGURO logo.png" width="300" height="300"></p>
<div align="justify">Hello, welcome to the GitHub repository of the MINAGURO team, which is competing in the World Robot Olympiad 2026 in the category of Future Engineers. Our team is made up of four Spanish students who built this robot on their school breaks with the aim of learning as much as possible.
<br> Guided by our passion for technology, we have created a vehicle that maybe doesn´t work as we would like to, but reflects all of our hard work and time spent on it.
 
  ## TABLE OF CONTENTS
· [Daily documentation](#daily-documentation)
<br>· [The Team](#the-team)
<br>· [Our Robot](#our-robot)
<br>· [Components used](#components-used)
<br>· [Software](#software)
<br>· [Our YouTube Channel](#Our-YouTube-Channel)

### Daily documentation
* **04/03/2026:** We began dividing up the work among the group, agreeing that Miguel and Rocío would handle the robot and the documentation, and Natalia and Guillermo would handle the programming. We also discussed the general features of the project. After watching videos of models from previous years and given that the robot’s maximum dimensions are 30x20 cm (which we felt was too large), we decided to try to make it as small as possible, since smaller robots tend to be more mobile and would also make it easier to avoid obstacles. Regarding the choice of the base board, we had four options: Raspberry Pi, Arduino R3, and Arduino R4 (with and without Bluetooth/Wi-Fi modules). Of these, we chose the Arduino R4 Minima (without Bluetooth/Wi-Fi) because it has a much faster protocol and more memory, and because the C++ used is a programming language we were already familiar with, which would make it easier for us to program; furthermore, it is compatible with the HUSKYLENS camera we already had and decided to use.  

* **05/03/26:** We looked for components in our classroom that could be used to build the robot and researched strategies from previous years on GitHub. 

* **06/03/26:** We decided on a basic strategy for the first and second challenges:  
  * First challenge:</ins> do not use HUSKYLENS; navigate as close as possible to the interior partitions to speed up the process; detect walls using distance sensors.  
  * Second challenge:</ins> use HUSKYLENS to detect obstacles and record their color, and distance sensors to measure the distance to the walls. 

* **09/03/26:** We researched the best way to move the robot; to do this, we looked at different models of remote-controlled cars, past projects we found in class, and GitHub repository files. In the end, we concluded that it would be best to have four wheels: two in front to control steering and two in the back to move it.  

* **10/03/26:** While reading the contest rules, we ran into a problem; we realized we couldn’t use a motor for each wheel, so we explored how we could drive both wheels with a single motor while still allowing them to operate independently in order to navigate curves. Ultimately, we agreed that the best solution would be to use a mechanical differential.  

* **11/03/26:** We searched and asked acquaintances for a differential or an old remote-controlled car to use in the project. Since no one had one, we started looking on different websites for a cheap, small differential that we could use for our robot. Finally, we settled on a front-axle differential from a remote-controlled robot that we found on AliExpress (even though we’ll be using it for the rear axle, since that doesn’t affect us) because it’s standard quality, inexpensive, and shipping isn’t too slow.  

* **12/03/26:** We discussed the distance sensors we’re going to use. In class, we have the following types: 
  * HC-SR04:</ins> ultrasonic distance sensor, works at a distance of up to four meters, digital pin connection, less accurate, sensitive to different types of surfaces and noise, very bulky.   
  * CJVL53L0XV2:</ins> laser distance sensor, works at a distance of up to two meters, I2C connection, high precision, compact, very low power consumption.  
  * TOF10120:</ins> laser distance sensor, operates at a range of up to 1.8 meters, I2C and UART connectivity, fast readings, large 10cm blind spot.  
With all this in mind, we decided to try the CJVL53L0XV2 laser sensors, as they offer the most benefits; we also decided to use three of them (one in front and two on each side) so we can measure the distance to the exterior walls at the front and the distance to the central partition on the sides.  

* **13/03/26:** We remembered that both HUSKYLENS and the laser distance sensors use the I2C protocol, so we decided to check that the addresses they use do not conflict. Once we verified this, we realized we had forgotten that, since the three distance sensors we plan to use are identical, they all use the same address. After writing a program to change the bus address and failing to get it to save, we agreed that having to change the address every time the program starts would waste time and add complexity to the program; so we decided to come up with another strategy individually and then pool our ideas.  

* **16/03/26:** After pooling all our ideas, we decided that the best option would be to use the HC-SR04 distance sensors, which, although less precise, we were already familiar with—an advantage when it comes to programming. Meanwhile, we began studying the HUSKYLENS AI camera, specifically its different modes, to see which one would be most useful to us. 

* **17/03/26:** We discussed how we could power the robot. We have eight rechargeable lithium batteries (model SAMSUNG ICR18650-26FU). We used this type of battery last year to build a PRINTBOT Evolution BQ robot, so based on that experience, we considered the best way to use them to ensure optimal battery life and minimize the space they occupy. We’re going to connect two cells in series to get 3.7 + 3.7 = 7.4 V, although when fully charged they actually reach 8.4 V. However, that voltage is ideal for powering the Arduino via Vin and for powering the drive servo directly from the batteries. For the Huskylens module, we plan to power it from the Arduino, but we’ll need to run tests because it has high power consumption. As for capacity, we need to look at the power consumption of each component and add them up to see how long they’ll last. 

<img src="COMPONENTS/BATERIAS_SAMSUNG.jpg" alt="Baterías">

* **18/03/26:** We looked for LEGO pieces in the sets we have in class for both the drive and steering wheels, as well as for the front-wheel steering system. To design the latter, we drew inspiration from how the steering systems of most remote-controlled cars are built and created a diagram of how we could assemble it using the pieces we have.   

* **19/03/26:** We assembled the steering system using LEGO pieces and a servomotor we had in class. Additionally, since we had already reviewed all of HUSKYLENS’s functions, we agreed that the most useful ones would be object recognition and color recognition, so we began researching these in greater depth and studying the library we found in its GitHub repository. 

* **20/03/26:** We created a program to rename the objects and colors we captured with the camera, since we thought this would make it easier to refer to the objects both within the rest of the program and visually on the camera screen. In doing so, we realized we had a problem: when we set HUSKYLENS to object detection mode, it always detected an object, even if the recorded objects weren’t visible. Since in this mode HUSKYLENS always had to have an object located, even if it didn’t exist, we decided it would be better to forget about using it and change our strategy for the second challenge. We will try to complete it by using the distance sensors both to maintain the distance from the central wall and to detect obstacles and steer toward them, and HUSKYLENS to determine the color of said obstacle. 

* **23/03/26:** Since we received the differential, we’ve been testing it; in doing so, we noticed that because it was new, the gears had trouble meshing properly—in other words, it didn’t run smoothly and fluidly. So we took it apart, lubricated it, and wore down the gear teeth by spinning them with a drill. On the other hand, since we now have the differential, from all the wheels we managed to collect, we chose the ones that worked best with both mechanisms. Finally, for the drive wheels, we chose larger ones because the bigger the wheels, the further the robot moves, and to match the size of the differential; and for the steering wheels, we chose smaller ones because we didn’t have any others of the same size. 

* **24/03/26:** We attached a 360° servo motor we have in class to the differential to check its speed, and we all agreed that it was moving too slowly. Therefore, we decided to increase the speed using a gear system. To do this, since we don’t have any gears that fit perfectly with the differential, we decided to design one in 3D and attach another one from the classroom LEGO kit. We also took the opportunity to design some couplings to attach the wheels to the differential.  

* **25/03/26:** We continued working on the 3D designs and researching HUSKYLENS. 

* **26/03/26:** We continued working on the 3D designs and created a program that moves a servo when HUSKYLENS detects an object in the center of the camera’s field of view; we did this simply to test whether we can use the camera to determine the object’s position in addition to detecting its color. 

* **27/03/26:** We finished the 3D designs and sent them to print on the school’s 3D printer. Additionally, after creating the previous program, we decided it might be a good idea to use coordinates instead of the object’s approximate position; therefore, we wrote a program that displays the center coordinates on the serial monitor. 

* **08/04/26:** We drew a diagram of how we want to assemble our robot and how we’re going to arrange all the components. We placed the HUSKYLENS at the front to detect colors, positioned a distance sensor on each side so we can measure using any of the four depending on what’s most useful, and placed the batteries under a platform with the wheels (and their respective servomotors), since this saves space and allows us to arrange the board and components more neatly above that platform. On the other hand, we considered different material options for the base, such as wood, plastic (3D printer), and a sheet of foam board we found in class. In the end, we decided that the foam board was the best option, since wood was very difficult for us to work with and would take more time, and 3D printing would also require a significant time investment (which would reduce our ability to test the program) and require us to have a clear understanding of all the component positions (something we weren’t 100% sure of yet). Even so, we decided this would be a temporary solution, and once we had everything figured out, we would make a 3D-printed base. 
<br> <img src="IMG_3713.jpeg" alt="DiseñoRobot1" width="350" height="300">    <img src="IMG_3714.jpeg" alt="DiseñoRobot2" width="350" height="300">

* **09/04/26:** Using a clamp meter, we measured how much power our robot would consume to determine whether we could use the battery module we had chosen. We found that the HUSKYLENS camera uses between 230 and 420 mA, the Arduino R4 board consumes 100 mA, the HC-SR04 consumes 15 mA, the microservo consumes 200 mA, and the RC servo consumes 700 mA. Therefore, our robot would consume a total of 1215 mA, which would give us just over two hours of runtime. Theoretically, that would be the robot’s total power consumption, but in reality, we measured that the robot consumes 500 mA, so those batteries, which have a capacity of 2600 mAh, should power the robot for more than 5 hours. Meanwhile, we began preparing the wiring for the distance sensors and the servo motors. However, we noticed that the Huskylens module sometimes reboots. We think this is because the Arduino board isn’t able to provide enough power, and we can’t connect it directly to the batteries since the module doesn’t support 8.4 V. While searching for information, we found a type of regulator called the LM7805 that steps down the voltage to 5 V. We’ve decided to use it to power the Huskylens module.  

* **10/04/26:** We assembled the robot on the temporary base, trying to pack all the components as tightly as possible. We used hot glue because we had it in the classroom; it bonds strongly to the components we’re using, allows us to attach and detach components easily, and doesn’t damage them. During assembly, we had to cut a hole in the board to mount the 180° servo so it would align with the height of the wheels. Once the entire robot is assembled, we create a program to control it with a joystick and check the maximum and minimum values for each servo. The data we have for the servo are: 
  * Voltage: 4.8–8.4 V / Imax = 1.2 A / Maximum torque: 14 kg·cm / N = 65 rpm  
  * For the transmission, we have tested various LEGO gears. The differential has a 12/30 reduction ratio, meaning it reduces the speed by a factor of 2.5. Therefore, we need to multiply the speed between the servo and the differential. Through testing, we found that with a 40-tooth gear on the servo and a 13-tooth gear on the differential input, the vehicle achieves an appropriate speed—neither too fast nor too slow.  
  * Wheel speed calculation: V = 65 × (40/13) × (12/30) = 80 rpm = 1.333 rev/s  
  * The wheels have a diameter of 43 mm and a circumference L = π × 43 = 135 mm  
  * The vehicle’s speed is V = 1.3333 × 0.135 = 0.18 m/s. We have verified this data with a stopwatch, and it is correct. 

<br> <img src="OTHER /prototipo1.jpg" alt="prototipo1" width="320" height="370">

* **13/04/26:** We wrote a program using the distance sensors to make the rear servo move when an object is detected. In doing so, we realized that the library we had always used for these sensors isn’t compatible with the Arduino R4 Mini board, so we looked for another one. The other library we found that was compatible required a common pin to connect all the “triggers” from all the ultrasonic sensors. To do this, we rewired the setup by soldering all the trigger wires from the three sensors together and connecting them to a single pin.

* **14/04/26:** We started creating a basic program to try to navigate around the inside of the parking garage. As we continued testing the programs, we noticed that the robot was moving slower than we’d like, so we decided to increase its speed using a LEGO gear system we have in class. When we incorporated it, we saw that it wasn’t working well because the robot was turning jerkily, so we had to reduce the speed a bit. We thought it was a software issue, so we’re trying to fix it. 

<img src="OTHER /sistema_engranajes.jpg" alt="sistema de engranajes" width="500" height="550">

* **15/04/26:** We were unable to fix the error by modifying the code, so we decided to change the gear system, this time using only one gear; as a result, it now moves slower than before, but faster than it did at the start. We also added a servo to the HUSKYLENS, as we believe it’s a good idea to use one because we think it has a narrow field of view, and with the servo attached, we’ll be able to rotate the camera and widen the angle. As for the program, the robot manages to turn around, but it makes very sharp turns, and when it gets too close, it crashes into the wall; we’re going to try to fix that. 

* **16/04/26:** We continue to plan our programs with the possibility of starting either to the right or to the left in mind, trying to check which way we’re going before leaving the parking lot. We have also added another HC-SR04 sensor at the rear to measure the distance to the parking space divider, making it easier for the program to exit the parking space. 

* **17/04/26:** We continued working on the programs, while also exploring options for exiting the parking lot; to do this, we drew inspiration from how participants in previous years had parked. During this process, we came across a robot that used a plastic rod that didn’t interfere with obstacles but allowed it to extend the robot’s length—and, therefore, the length of the parking space. Since we liked this idea, we decided to implement it and devise a parking strategy, taking into account that we now had a greater distance than we initially thought. With that in mind, we decided to create a program. 

* **20/04/26:** Since the front wheels keep jerking, we thought the 180-degree servo might be experiencing interference, so we decided to replace it with a better one we already had. It seems to work better, but it still malfunctions quite a bit. As for the program, we managed to get it to exit the parking space; so all that’s left is to have it face the central partition. We also tried using a magnetometer (compass) from class to get a reading of the robot’s position, with the idea of using it for various tasks like exiting the parking lot or making more precise turns. However, upon checking the readings, we saw that the coordinate intervals weren’t consistent and, therefore, didn’t match reality; we decided to order another one. 

* **21/04/26:** To try to fix the jerking issue, we installed some laser distance sensors and disabled the ultrasonic sensors. We tested them using a box (as if the box were the center of the board), and it worked quite well most of the time, except for a few instances where it didn’t read the position correctly. Next, we tested it on the official competition board; this time, 70% of the time it didn’t read the curves correctly and didn’t take the right direction. After further testing, we concluded that the problem with these sensors was the reflection of light off the black paint on the walls; therefore, they didn’t solve our initial problem. 

* **22/04/26:** We realized that if we connect HUSKYLENS directly to the board, the robot keeps stopping because the Arduino isn't able to power HUSKYLENS properly, causing it to reboot. From now on, we’ll power HUSKYLENS directly from the batteries using a voltage regulator based on the LM7805 circuit, which converts the batteries’ 8.4 volts to 5 volts—enough to power the camera on its own. On the other hand, since we had made so many changes to the robot’s chassis, the base was no longer stable or secure; so we decided it was time to design the final version in 3D. We drew a hand-drawn sketch of where the components would be placed and began designing it in 3D. 

* **23/04/26:** We continued working on the chassis design.  

* **24/04/26:** We are proceeding to replace all the sensors. We have once again used hot glue for the same reasons: it provides a strong, quick bond, is easy to apply and remove, and does not damage the components. In the process, we encountered several design issues that we resolved manually by removing material with a soldering iron to heat and melt the material into the desired shape, since we didn’t have enough time to redesign and print another part. Even so, we will redesign it in 3D so that the robot is perfectly reproducible. Also, since we were going to change the base, we decided to switch the gear ratio to a larger one to reduce the speed slightly. 

* **25/04/26:** We continued assembling the new base and also replaced some of the component cables. We decided to attach the distance sensors to a foam board using hot glue, since hot glue allows us to attach and remove the components easily without damaging them. 

* **27/04/26:** We installed the new magnetometer on the robot using a foam board rod to prevent interference issues and added an LCD display so we could view its readings without having to connect to the computer; once this was done, we began testing. The first few tests went well, but after about 10, it stopped working; we also tried the other one that came with the purchase, and the problem was the same as with the first one. We agreed to try one last time, so we ordered one final magnetometer.  

* **30/04/26:** We no longer have time to move forward with the challenge, so we began preparing all the documentation.  

* **04/05/26:** We are still working on the documentation. 

* **19/05/26:** We are working on the final program and retouching the documentation.

* **26/05/26:** We’ve gone over the rules again to avoid any further misunderstandings and have established a new strategy for the challenges. First, we decided that we would complete the open challenge using only the distance sensors. For the second challenge, the obstacle course, we decided to use the HUSKYLENS camera and minimize the use of the sensors. If we manage to complete this second challenge—and knowing that the first one already works as is—we’ll try the free challenge using the HUSKYLENS camera with minimal sensor involvement. We’ve tested the free challenge part, and it works perfectly. We’d just need to count laps and park, but due to time constraints, we’re going to prioritize the obstacle challenge. 

* **27/05/26:** After testing the HUSKYLENS, we found that I2C communication causes fewer issues than using the serial port. We also discovered that the HUSKYLENS must be pointed downward because, when testing it with the program, we noticed it detects objects outside the field of view, which could make it difficult for us to complete the challenge. As for the servo that came with the HUSKYLENS, we disconnected it because it was interfering with the system. With this information, we decided to place the HUSKYLENS module in an elevated position so it can look forward, but only at the playing field. Additionally, we had a problem with the Arduino R4 Mini board; it broke and stopped working, so we decided to use the Arduino R4 board with Wi-Fi/Bluetooth that we had in class, but we decided not to use the Wi-Fi/Bluetooth mode since it violates the rules. 

### Mechanical Design
This section is dedicated to the robot’s mechanical components: the list of parts used in its construction and the 3D-printed parts we designed and printed.

#### Parts List  
Here is a list of all the parts we used, including an image, their specific function in the robot, and a purchase link: 

| Component | Quantity | Image | Function | Purchase link |
| :---: | :---: | :---: | :---: | :---: |
| SPT5632-360 | 1 | <img src="COMPONENTS/SPT5632-360.jpg" width="150" height="120"> | Robot mobility | <a href="https://es.aliexpress.com/item/4001189631333.html?spm=a2g0o.detail.pcDetailBottomMoreOtherSeller.21.56e3gBQagBQake&gps-id=pcDetailBottomMoreOtherSeller&scm=1007.40050.354490.0&scm_id=1007.40050.354490.0&scm-url=1007.40050.354490.0&pvid=5e6d47a7-7388-4b21-b59b-0061086f9c61&_t=gps-id%3ApcDetailBottomMoreOtherSeller%2Cscm-url%3A1007.40050.354490.0%2Cpvid%3A5e6d47a7-7388-4b21-b59b-0061086f9c61%2Ctpp_buckets%3A668%232846%238110%231995&pdp_ext_f=%7B%22order%22%3A%22371%22%2C%22eval%22%3A%221%22%2C%22sceneId%22%3A%2230050%22%2C%22fromPage%22%3A%22recommend%22%7D&pdp_npi=6%40dis%21EUR%2110.79%2110.79%21%21%2184.16%2184.16%21%40211b6c1917779734902752140ebb0a%2110000015232527414%21rec%21ES%21135718878%21X%211%210%21n_tag%3A-29919%3Bd%3A2676a4e6%3Bm03_new_user%3A-29895&utparam-url=scene%3ApcDetailBottomMoreOtherSeller%7Cquery_from%3A%7Cx_object_id%3A4001189631333%7C_p_origin_prod%3A"> 360º servo link</a> |
| MS18 | 1 | <img src="COMPONENTS/MS18.jpg" width="150" height="120"> | Robot direction system | <a href="https://es.aliexpress.com/item/4001189631333.html?spm=a2g0o.detail.pcDetailBottomMoreOtherSeller.21.56e3gBQagBQake&gps-id=pcDetailBottomMoreOtherSeller&scm=1007.40050.354490.0&scm_id=1007.40050.354490.0&scm-url=1007.40050.354490.0&pvid=5e6d47a7-7388-4b21-b59b-0061086f9c61&_t=gps-id%3ApcDetailBottomMoreOtherSeller%2Cscm-url%3A1007.40050.354490.0%2Cpvid%3A5e6d47a7-7388-4b21-b59b-0061086f9c61%2Ctpp_buckets%3A668%232846%238110%231995&pdp_ext_f=%7B%22order%22%3A%22371%22%2C%22eval%22%3A%221%22%2C%22sceneId%22%3A%2230050%22%2C%22fromPage%22%3A%22recommend%22%7D&pdp_npi=6%40dis%21EUR%2110.79%2110.79%21%21%2184.16%2184.16%21%40211b6c1917779734902752140ebb0a%2110000015232527414%21rec%21ES%21135718878%21X%211%210%21n_tag%3A-29919%3Bd%3A2676a4e6%3Bm03_new_user%3A-29895&utparam-url=scene%3ApcDetailBottomMoreOtherSeller%7Cquery_from%3A%7Cx_object_id%3A4001189631333%7C_p_origin_prod%3A"> 180º Servo direction link</a> |
| HC-SR04 | 2 | <img src="COMPONENTS/HC-SR04.jpg" width="150" height="120"> | Measure distances | <a href="https://es.aliexpress.com/item/1005010373195248.html?spm=a2g0o.productlist.main.1.4afa606fVeuEr0&algo_pvid=54f18ed3-18b2-4b6a-8dbc-cd5d3668bcef&algo_exp_id=54f18ed3-18b2-4b6a-8dbc-cd5d3668bcef-0&pdp_ext_f=%7B%22order%22%3A%2280%22%2C%22eval%22%3A%221%22%2C%22fromPage%22%3A%22search%22%7D&pdp_npi=6%40dis%21EUR%218.03%210.99%21%21%2162.67%217.74%21%40211b819117780681213312200e1d8a%2112000052180896573%21sea%21ES%210%21ABX%211%210%21n_tag%3A-29910%3Bd%3Aa4bac484%3Bm03_new_user%3A-29895%3BpisId%3A5000000203538426&curPageLogUid=QstesSY3YdXa&utparam-url=scene%3Asearch%7Cquery_from%3A%7Cx_object_id%3A1005010373195248%7C_p_origin_prod%3A"> Ultrasonic sensor link</a> |
| HC-SR04RC | 2 | <img src="COMPONENTS/HC-SR04RC.jpg" width="150" height="120"> | Measure distances | <a href="https://www.tiendatec.es/maker-zone/modulos/2785-sensor-ultrasonico-hc-sr04rc-con-chip-rcwl-9616-gpio-uart-i2c-y-1-wire.html"> Ultrasonic sensor link</a> |
| HUSKYLENS | 1 | <img src="COMPONENTS/HUSKYLENS.webp" width="150" height="120"> | Object detection | <a href="https://www.amazon.es/HUSKYLENS-inteligente-Seguimiento-Reconocimiento-etiquetas/dp/B089GLJHZD/ref=asc_df_B089GLJHZD?mcid=36800d9b99ce32ed8669f6a3e4ec2f84&tag=googshopes-21&linkCode=df0&hvadid=704489408389&hvpos=&hvnetw=g&hvrand=16285365096963908748&hvpone=&hvptwo=&hvqmt=&hvdev=c&hvdvcmdl=&hvlocint=&hvlocphy=9198870&hvtargid=pla-1463570363676&hvocijid=16285365096963908748-B089GLJHZD-&hvexpln=0&th=1"> AI Vision sensor link</a> |
| Rocker Switch | 1 | <img src="COMPONENTS/Rocker Switch.avif" width="150" height="120"> | Power on and off robot switch | <a href="https://es.aliexpress.com/item/1005008525408190.html?spm=a2g0o.productlist.main.17.431d74493KVuzo&algo_pvid=e9f9c09c-5089-4439-be0e-f05956214450&algo_exp_id=e9f9c09c-5089-4439-be0e-f05956214450-14&pdp_ext_f=%7B%22order%22%3A%22653%22%2C%22eval%22%3A%221%22%2C%22fromPage%22%3A%22search%22%7D&pdp_npi=6%40dis%21EUR%211.85%210.99%21%21%2114.40%217.69%21%402103890117771122923863735ec053%2112000045558767272%21sea%21ES%210%21ABX%211%210%21n_tag%3A-29910%3Bd%3A25dad6b%3Bm03_new_user%3A-29895%3BpisId%3A5000000204276354&curPageLogUid=KGO1IXkqj9GF&utparam-url=scene%3Asearch%7Cquery_from%3A%7Cx_object_id%3A1005008525408190%7C_p_origin_prod%3A"> Rocker switch link</a> |
| Pull down button | 1 | <img src="COMPONENTS/Pull down button.jpg" width="150" height="120"> | Starter robot program button | <a href="https://es.aliexpress.com/i/1005002576288170.html"> Pull down button link</a> |
| Samsung battery 2600mAh | 4 | <img src="COMPONENTS/Samsung battery 2600mAh.webp" width="150" height="120"> | Batteries | <a href="https://bateriasonline.com/es/baterias-litio-recargable/bateria-litio-samsung-icr-18650-26j-2600mah-samsung-baterias-litio-recargable.html?srsltid=AfmBOop1R_bLE43Q_vkAh_JRYLJcKs3b_JRSsD6eFUK0Ot32YkWfNtN-"> Samsung battery link</a> |
| Lego wheels 30,4x14 | 2 | <img src="COMPONENTS/Lego wheels 30.4 x 14.webp" width="150" height="120"> | Directional wheels | <a href="https://www.toypro.com/es/product/33208/rueda-18-mm-d-x-14-mm-con-agujero-para-pasador-pernos-falsos-y-radios-poco-profundos-con-llanta-negra-30-4-x-14-banda-de-rodadura-desplazada-55981-30391/gris-azulado-claro?srsltid=AfmBOooMGv7-eRncxEPbJrWFwlcMzZU4-aFSelHhvuYBHHatj6sHPQM1"> Directional wheels link</a> |
| Lego wheels 13x24 | 2 | <img src="COMPONENTS/Lego wheels 13 x 24.jpg" width="150" height="120"> | Drive wheels | <a href="https://www.steinpalast.eu/en/1-x-lego-brick-light-gray-wheel-30mm-d.-x-13mm-13-x-24-model-team-with-black-tire-13-x-24-model-team-2695-4141535-2696-269626-2695c01"> Drive wheels link</a> |
| Servo arm | 1 | <img src="COMPONENTS/Servo arm MS18.avif" width="150" height="120"> | Servo direction arm | <a href="https://es.aliexpress.com/item/1005012158832496.html?spm=a2g0o.productlist.main.4.1edfnKTwnKTwnB&algo_pvid=5417366f-c791-4e53-a569-c27a98fc2162&algo_exp_id=5417366f-c791-4e53-a569-c27a98fc2162-3&pdp_ext_f=%7B%22order%22%3A%228%22%2C%22spu_best_type%22%3A%22price%22%2C%22eval%22%3A%221%22%2C%22fromPage%22%3A%22search%22%7D&pdp_npi=6%40dis%21EUR%216.85%212.65%21%21%2153.52%2120.74%21%40210384b217781457573274739eee2a%2112000057659670774%21sea%21ES%210%21ABX%211%210%21n_tag%3A-29910%3Bd%3Aa4bac484%3Bm03_new_user%3A-29895%3BpisId%3A5000000205922472&curPageLogUid=1s0ozgZzGPqi&utparam-url=scene%3Asearch%7Cquery_from%3A%7Cx_object_id%3A1005012158832496%7C_p_origin_prod%3A"> 180º micro servo link</a> |
| Gear teeth Lego 4285634 | 1 | <img src="COMPONENTS/Gear teeth Lego 4285634.jpg" width="150" height="120"> | Gear teeth transmission | <a href="https://www.electricbricks.com/lego-piezas-lego-technic,-engranaje-gris-claro-azulado-engranaje-dientes-p-425.html"> Gear teeth link </a>|
| Lego structure piece 4495931 | 3 | <img src="COMPONENTS/Lego structure piece 4495931.webp" width="150" height="120"> | Maintain direction structure | <a href="https://www.toypro.com/es/product/3937/liftarm-1-x-7-grueso/gris-azulado-oscuro?srsltid=AfmBOorBuWPTbd0rp7J5CSv3HlYMqGJvfZ5qkVGlDqX8xSTJyZnriyeG"> Lego structure piece link </a>  |
| Arduino R4 MINIMA | 1 | <img src="COMPONENTS/Arduino_R4 MINIMA.jpg" width="150" height="120"> | Robot controller | <a href="https://www.amazon.es/Arduino-UNO-Minima-ABX00080-Connector/dp/B0C78K4CD4"> Arduino R4 MINIMA link</a> |
| Lego structure piece 4210686 | 2 | <img src="COMPONENTS/Lego structure piece 4210686.avif" width="150" height="120"> | Connect directional wheels and connect them with the structure | <a href="https://es.aliexpress.com/item/1005011819503855.html?src=google&src=google&albch=shopping&acnt=439-079-4345&isdl=y&slnk=&plac=&mtctp=&albbt=Google_7_shopping&aff_platform=google&aff_short_key=UneMJZVf&gclsrc=aw.ds&albagn=888888&ds_e_adid=&ds_e_matchtype=&ds_e_device=c&ds_e_network=x&ds_e_product_group_id=&ds_e_product_id=es1005011819503855&ds_e_product_merchant_id=107567352&ds_e_product_country=ES&ds_e_product_language=es&ds_e_product_channel=online&ds_e_product_store_id=&ds_url_v=2&albcp=20542360520&albag=&isSmbAutoCall=false&needSmbHouyi=false&gad_source=1&gad_campaignid=17340214516&gbraid=0AAAAACbpfvYuNwQ1V3xDib2TlBxpflVYs&gclid=EAIaIQobChMIqZGIl6aflAMVnI5oCR199jqyEAQYAiABEgLzT_D_BwE"> Lego structure2 piece link </a> |
| Lego piece 4514554 (3 modules) | 3 | <img src="COMPONENTS/Lego piece 4514554.webp" width="150" height="120"> | Connect the directional | <a href="https://www.toypro.com/es/product/1776/technic-pin-largo-sin-estrias-de-friccion-longitudinales/tan?srsltid=AfmBOoqqbuAxeT4ULrI73zVTMFH8t7_HuYIcuJz_XVb1vpj3KXK-qs8D"> Lego piece 4514554 link </a> |
| Lego piece 4514553 (3 modules) | 4 | <img src="COMPONENTS/Lego piece 4514553.webp" width="150" height="120"> | Connect the directional structure and connect it with chassis | <a href="https://www.toypro.com/es/product/2247/technic-pin-largo-con-estrias-de-friccion-longitudinales/azul?srsltid=AfmBOoqgtvS341U5QKuqMzuibB6NDnAIcyx8KQwD8Fsvz7nsYZRyQv2s"> Lego piece 4514553 link </a> |
| Lego piece 4211807 (2 modules) | 2 | <img src="COMPONENTS/Lego piece 4211807.webp" width="150" height="120"> | Connect the directional structure | <a href="https://www.toypro.com/es/product/756/technic-pin-sin-estrias-de-friccion-longitudinales/gris-azulado-claro?srsltid=AfmBOoqCiqgFyXZBCIu2rkTYcivDDJrr15Kn4coFCvSYRXdTXMta3fcI"> Lego piece 4211807 link </a> |
| Lego piece 4495931 (2 modules) | 1 | <img src="COMPONENTS/Lego piece 4495931.webp" width="150" height="120"> | Connect directional structure | <a href="https://www.toypro.com/es/product/1152/technic-pasador-de-eje-sin-estrias-de-friccion-longitudinalmente/tan?srsltid=AfmBOooZH7rHaNTKpPFgEphyQGzF2_0XQoAJPNM4Ki51-C_wdsH27EJX"> Lego piece 4495931 link </a> |
| Lego piece 4560175 | 1 | <img src="COMPONENTS/Lego piece 4560175.webp" width="150" height="120"> | Connect directional structure | <a href="https://www.toypro.com/es/product/2210/technic-pasador-largo-con-estrias-de-friccion-longitudinales-y-orificio-central-para-el-pasador/gris-azulado-claro?srsltid=AfmBOorSUHxEOJ2i5-85EPdvQcjwU1bGyXjPJdgFHhxL5Bt5vq-A_alA"> Lego piece 4560175 link </a> |
| Lego piece 4107767 | 2 | <img src="COMPONENTS/Lego piece 4107767.webp" width="150" height="120"> | Connect directional wheels with directional structure | <a href="https://www.toypro.com/es/product/577/eje-y-conector-de-pin-n-6-90/negro?srsltid=AfmBOorXiZJun_k-E2hKjYEJTn1MJVnT7njdhTR7xKyNWakuH3zyl84c"> Lego piece 4107767 link </a> |
| Lego piece 4107085 | 2 | <img src="COMPONENTS/Lego piece.webp" width="150" height="120"> | Connect directional structure | <a href="https://www.toypro.com/es/product/152/eje-y-conector-de-pin-n-1/negro?srsltid=AfmBOor2gTwMQ0SjiqnX9UFra149tetnTWeLNWH5GG9X5Cj_pXMF2bMb"> Lego piece 4107085 link </a> |
| LM7805CT | 2 | <img src="COMPONENTS/LM7805CT.webp" width="150" height="120"> | Supply energy to huskylens directly of the batteries | <a href="https://richelectronics.co.uk/product/motorola-mc7805ct-3-terminal-positive-voltage-regulator-5-pieces-oma77"> LM7805CT link </a> |
| Electrolytic condenser 0,1 microfarad | 1 | <img src="COMPONENTS/Electrolytic condenser 0,1 microfarad.webp" width="150" height="120"> | (maker recommendation) | <a href="https://www.nyerekatech.com/shop/0-1%C2%B5f-50v-electrolytic-capacitor/?srsltid=AfmBOoo2jnLNwXlnsHoz9CriiyzsWqAPUzHO8ErVziPrRmL6AmUMi83d"> Electrolytic condenser link </a> |
| Electrolytic condenser 0,33 microfarad | 1 | <img src="COMPONENTS/Electrolytic condenser 0,33 microfarad.webp" width="150" height="120"> | (maker recommendation) | <a href="https://www.tme.eu/en/details/uvy2dr33med/tht-electrolytic-capacitors/nichicon/"> Electrolytic condenser link </a> |
| Circuit board | 1 | <img src="COMPONENTS/Circuit board.webp" width="150" height="120"> | Connect huskylens with the LM7805CT and then with batteries | <a href="https://www.pccomponentes.com/goobay-regleta-para-conexion-de-cables-electricos-de-10a-10mm-blanco?campaigntype=eshopping&campaignchannel=shopping&gad_source=1&gad_campaignid=12885548290&gclid=EAIaIQobChMI__yQzemhlAMVr3JBAh075B8YEAQYBSABEgLyYvD_BwE"> Circuit board link </a> |
| Differential QBX01 1:12 | 1 | <img src="COMPONENTS/Differential.avif" width="150" height="120"> | It allows the drive wheels to rotate at different speeds on curves, preventing slippage | <a href="https://es.aliexpress.com/item/1005005425198232.html?spm=a2g0o.productlist.main.1.5afe3DuB3DuBQD&algo_pvid=89b2de5b-abad-4232-8ccb-d5e73895d3df&algo_exp_id=89b2de5b-abad-4232-8ccb-d5e73895d3df0&pdp_ext_f=%7B%22order%22%3A%22329%22%2C%22spu_best_type%22%3A%22price%22%2C%22eval%22%3A%221%22%2C%22fromPage%22%3A%22search%22%7D&pdp_npi=6%40dis%21EUR%219.53%215.53%21%21%2174.34%2143.14%21%402103892f17779733213802821e83c8%2112000033106328679%21sea%21ES%210%21ABX%211%210%21n_tag%3A-29910%3Bd%3A4f6c22e4%3Bm03_new_user%3A-29895%3BpisId%3A5000000205205646&curPageLogUid=a9DwnAg9v3GZ&utparam-url=scene%3Asearch%7Cquery_from%3A%7Cx_object_id%3A1005005425198232%7C_p_origin_prod%3A"> Differential link </a> |
| Baterie support | 1 | <img src="support.jpg" width="150" height="120"> | Is the support of the second batterie | We made it in class using a kind of cardboard and hot glue gun |
| Power Expansion Board Module | 1 | <img src="power bank batteries.png" width="150" height="120">  | It's a style of power bank where we've used the same Samsung batteries | <a href="https://es.aliexpress.com/item/1005001829484812.html?spm=a2g0o.detail.pcDetailTopMoreOtherSeller.3.3145BM7PBM7Pvs&gps-id=pcDetailTopMoreOtherSeller&scm=1007.40050.354490.0&scm_id=1007.40050.354490.0&scm-url=1007.40050.354490.0&pvid=aaef1a73-1862-4b0d-aa1e-1a9beffbe5b0&_t=gps-id%3ApcDetailTopMoreOtherSeller%2Cscm-url%3A1007.40050.354490.0%2Cpvid%3Aaaef1a73-1862-4b0d-aa1e-1a9beffbe5b0%2Ctpp_buckets%3A668%232846%238110%231995&pdp_ext_f=%7B%22order%22%3A%221076%22%2C%22eval%22%3A%221%22%2C%22sceneId%22%3A%2230050%22%2C%22fromPage%22%3A%22recommend%22%7D&pdp_npi=6%40dis%21EUR%212.06%212.06%21%21%212.34%212.34%21%402103909217800442825806414e0fc1%2112000017779552633%21rec%21ES%21135718878%21XZ%211%210%21n_tag%3A-29919%3Bd%3A2676a4e6%3Bm03_new_user%3A-29895&utparam-url=scene%3ApcDetailTopMoreOtherSeller%7Cquery_from%3A%7Cx_object_id%3A1005001829484812%7C_p_origin_prod%3A"> Power bank link </a> |

#### 3D Designs
These are the 3D designs we have created, which include: a custom-made chassis for all components, a gear to connect the differential to the 360-degree servo, a rear wheel adapter to connect the differential shaft to the wheels and a mount for the HUSKYLENS module:

| Component | Quantity | Image | Function | File link |
| :---: | :---: | :---: | :---: | :---: |
| Chasis in 3D | 1 | <img src="COMPONENTS/Chasis.png" width="150" height="120"> | Skeleton of the robot | [`CHASSIS.stl`](3D_DESIGNS/CHASSIS.stl) |
| Adapter wheels in 3D | 2 | <img src="COMPONENTS/Wheel adapter.png" width="150" height="120"> | Supply energy to huskylens directly of the batteries | [`GEAR_ADAPTER.stl`](3D_DESIGNS/GEAR_ADAPTER.stl) |
| Adapter gear in 3D | 1 | <img src="COMPONENTS/Gear adapter.png" width="150" height="120"> | Gearing with 360º servo gear | [`WHEEL_ADAPTER.stl`](Adaptador_rueda.stl) |

### Mobility design
This section includes the robot's torque and speed, the rationale behind its final configuration, as well as images of all its plans and the wiring diagram we created in TinkerCad using all the robot's components. 

Generally speaking, the robot has:

* An Arduino R4 board (chosen based on previous experience programming it) 
* Four HC-SR04 sensors (one at the front, one at the rear, and two on the sides, one on each side): the front and side sensors are mounted on top of the chassis on a small piece of foam board to...; the rear sensor is mounted underneath the chassis due to space constraints at the rear top of the chassis. The triggers for the four sensors are soldered to the same pin to save pins on the Arduino board, in case more components need to be connected. 
* Four Samsung batteries... two of which power the Arduino board directly... 
* A 360-degree servo that functions as a servo motor. 
* A transmission system made with LEGO gears and one made with 3D-printed parts that runs from the servo motor to the mechanical differential. 
* A mechanical differential equipped with two adapters for 3D printers to ensure a better fit on the wheels. 
* Four LEGO wheels (two larger and two smaller: the specific models are listed in the parts list). 
* Un sistema de dirección de LEGO (piezas usadas en la lista de componentes). 
* An 180-degree servo to move the LEGO steering system via an arm attached to a string that runs to the steering system. 
* A HUSKYLENS module for detecting obstacles. 
* A foam board frame for holding a couple of batteries. 
* A switch to turn on the robot. 
* A button to start the program.

#### Steering system 
The steering system used consists of:  

* A system made from LEGO bricks from our Technology class, because it’s easy to assemble and disassemble and can be put together fairly quickly in case modifications are needed, featuring two LEGO wheels that are smaller than the rear ones.  
* An 180-degree servo, since it’s easy to program and a larger turning angle wasn’t necessary given the system we built.  
* A servo arm with a string, to connect the LEGO steering system to the servo.

<table>
  <tr>
    <td align="center" width="33%">
      <img src="steering_system.JPG" width="305"/>
    </td>
    <td align="center" width="33%">
      <img src="steering_system2.JPG" width="305"/>
    </td>
    <td align="center" width="33%">
      <img src="steering_system3.JPG" width="305"/>
    </td>
  </tr>
</table>

If this steering turned too far in one direction, it would jam and could break. To prevent this, we adjusted the values using the steering servo calibration program so that this wouldn’t happen.  

<div align="center"><table>
  <tr>
    <td align="center" width="50%">
      <b>Micro servo 180</b><br>
      <img src="SERVO180_caract.jpg" width="350"/>
    </td>
    <td align="left" width="50%">
      <ul>
        <li>A:32mm</li>
        <li>B:23mm</li>
        <li>C:28,5mm</li>
        <li>D:12mm</li>
        <li>E:32mm</li>
        <li>F:19mm</li>
        <li>Speed:0,1sec</li>
        <li>Torque:2,5kg-cm</li>
        <li>Weight:14,7g</li>
        <li>Voltage:4,8-6V</li>
      </ul>
    </td>
  </tr>
</table></div>

#### Drive system
The motor system used consists of: 

* A 360-degree continuous-rotation servo (model listed in the parts list). 
* A gear system to transmit motion from the servo motor to the mechanical differential, consisting of a 40-tooth LEGO gear and a 13-tooth gear made with a 3D printer. The gear ratio is 12:30. 
* A mechanical differential. The differential was purchased from AliExpress based on an idea from a previous project in our Technology classroom. 
* Two 3D-printed adapters that connect the differential shafts to the LEGO wheels. 
* Two LEGO wheels larger than those in the steering system. 

The first 360-degree continuous rotation servo we installed caused smoothness issues when the robot moved, leading us to believe the problems were software-related; however, when it was replaced with another one we had in our classroom, the issues did not recur. 

The mechanical differential was a bit stiff to turn when it arrived. To make it turn more smoothly, we lubricated it with oil and turned it using a drill. 

The rear wheels are larger than the front wheels because the front wheels had to cover the height of the mechanical differential on their own; the front wheels already accounted for the height of the LEGO steering system.

#### Chassis design

The chassis has evolved based on the need to add or remove components, and depending on what was most practical for meeting the challenges. 

Initially, we used a sheet of foam board that was in the classroom, onto which we gradually added all the components. To attach the components, we used hot glue (because it has good adhesive properties, allows us to make modifications easily, and doesn’t damage the components). In fact, the first prototype was tested with a foam board base. 

The front is cut into a pointed shape to prevent it from coming into contact with any of the interior partition walls or those of the parking garage during the obstacle phase. 

<div align="center"><table>
  <tr>
    <td align="center" width="33%">
      <img src="prototype1.1.jpg" width="305"/>
    </td>
    <td align="center" width="33%">
      <img src="prototype1.2.jpg" width="305"/>
    </td>
    <td align="center" width="33%">
      <img src="prototype1.3.jpg" width="305"/>
    </td>
  </tr>
</table></div>

After confirming that this was the final base, we designed the chassis in 3D, printed it, and transferred the components from one base to the other. Although we thought this change might cause problems once everything was already assembled, there were none. 

<p align="center"><a src="3D_DESIGNS/CHASSIS.stl"><img src="COMPONENTS/Chasis.png" width="500"></a></p>

The initial layout of all the components was sketched by hand to give us an idea (photos attached): 

<div align="center"><table>
  <tr>
    <td align="center" width="50%">
      <img src="IMG_3713.jpeg" width="400"/>
    </td>
    <td align="center" width="50%">
      <img src="IMG_3714.jpeg" width="400"/>
    </td>
  </tr>
</table></div>

An important consideration regarding the robot’s balance was to place the heaviest components (the Arduino board, the batteries, the 360-degree servo) in the center of the chassis, maintaining a low and centralized center of mass. The batteries that directly power the 360-degree servo (explained in detail below) are located in a separate structure, as this was a last-minute modification.

### Power and Sensor Architecture 

This section covers the power supply, the wiring diagram created in TinkerCad, and everything related to the sensors. 

#### Power Supply 
The robot uses four Samsung ICR18650-26FU batteries as its power source. Two batteries power the Arduino R4 board, and the other two directly power the 360-degree servo motor. This prevents interference with the servo, allowing the robot to move smoothly. 

An energy estimate was calculated for all components to determine the appropriate batteries: 

* HUSKYLENS module: 230–420 mA. 
* Arduino R4 Minima board: 100 mA. 
* HC-SR04 sensors: 15 mA 
* 180-degree microservo: 200 mA 
* 360-degree continuous rotation servo: 700 mA 
* Total: 1215 mA 

Theoretically, this is the robot’s power consumption. However, after measuring the robot’s actual power consumption, it was 500 mA. Therefore, with two batteries (2600 mA), we have enough power for 5 hours. These were the initial calculations since we were only going to use two batteries. Finally, after verifying that using two batteries connected directly to the 360-degree servo and the HUSKYLENS module works as intended, we will now connect four batteries (5200 mA), which theoretically gives us: 

* Battery life for the 360° servo and the HUSKYLENS camera (8.4 V and 2600 mA): approximately 2.5 hours. 
* Battery life for the Arduino board (4.2 V and 5200 mA): approximately 16 hours. 

This means we need to be careful with the batteries for the 360° servo and the HUSKYLENS module because they may fail due to a lack of power. 

Based on this estimate and the availability of batteries in our class, we chose the Samsung ICR18650-26FU model. The main features of this model are:

<p align="center"><img src="COMPONENTS/BATERIAS_SAMSUNG.jpg" width="300"></p>

The batteries that power the board are placed in a dedicated space on the 3D-printed chassis. Initially, in the prototype with the foam board base, they were glued to the bottom of the base, as seen in the initial sketches of the component layout. Later, it was decided to create a custom-made 3D-printed space for them in that same location.

<div align="center"><table>
  <tr>
    <td align="center" width="50%">
      <img src="prototype1.2.jpg" width="300" height="350/>
    </td>
    <td align="center" width="50%">
      <img src="batteries1.JPG" width="400" height="350"/>
    </td>
  </tr>
</table></div>

The batteries that power the servo, being a last-minute modification, have been placed in a foam board structure on the upper rear of the robot. This also extends the parking length and allows us to exit the parking space in the obstacle course with more room to maneuver. 

<div align="center"><table>
  <tr>
    <td align="center" width="33%">
      <img src="batteries_structure1.jpeg" width="350"/>
    </td>
    <td align="center" width="33%">
      <img src="batteries_structure2.jpeg" width="350"/>
    </td>
    <td align="center" width="33%">
      <img src="batteries_structure3.JPG" width="350"/>
    </td>
  </tr>
</table></div>

To power the HUSKYLENS module, an LM7805 regulator has been included to step down the voltage from the batteries from 8.4 V to 5 V. Electrolytic capacitors have also been included as recommended by the manufacturer. 

#### Wiring Scheme
The wiring diagram used for assembling the robot is shown in the image below. It was created in TinkerCad based on previous experience using this program. Some components were not available in TinkerCad, so similar ones that met the necessary connection requirements were used, and their names were noted on the final diagram to avoid confusion:

#### Sensors 
The robot receives data from three main components: the Arduino R4 Minima board, the HC-SR04 sensors, and the HUSKYLENS module.  

The Arduino R4 Minima board was chosen because it has additional pins that other Arduino boards do not have, ensuring there are enough pins to connect all the components. However, after an accident in which this board stopped working, it was replaced with an Arduino R4 Wi-Fi/Bluetooth board because it has the same pins that we’ve been using from the start. The Wi-Fi and Bluetooth functions were not used to solve the challenges, as this violates the rules. This can be seen in the libraries downloaded from the final program. 

<div align="center"><table>
  <tr>
    <td align="center" width="50%">
      <img src="COMPONENTS/HUSKYLENS.webp" width="500" height="400"/>
    </td>
    <td align="center" width="50%">
      <img src="PLACA_caract.png" width="900" height="400"/>
    </td>
  </tr>
</table></div>

The HC-SR04 sensors were chosen after considering three types of sensors: the HC-SR04, the CJVL53L0XV2 (which use lasers), and the TOF10120 (which also use lasers). Initially, the CJVL53L0XV2 was chosen, although it was later replaced due to programming issues. The HC-SR04, although less efficient, is easier to program, and we had used it before. 

We started by installing three sensors (two on the sides and one at the front), because we thought that would be enough to park and navigate turns without any problems. However, adding a fourth sensor—mounted on the lower rear of the robot—provided more accurate measurements that helped us overcome challenges (specifically the parking portion of the obstacle course) more easily. 

<div align="center"><table>
  <tr>
    <td align="center" width="50%">
      <img src="COMPONENTS/HC-SR04RC.jpg" width="500"/>
    </td>
    <td align="left" width="50%">
      * Operating Voltage: 5V DC
      * Quiescent Current: < 2mA
      * Operating Current: 15mA
      * Measuring Range: 2–450 cm
      * Accuracy: ±3 mm
      * Beam Angle: 15°
      * Ultrasonic Frequency: 40 kHz
      * Minimum TRIG trigger pulse duration (TTL level): 10 μs
      * Output ECO pulse duration (TTL level): 100–25,000 μs
      * Dimensions: 45 × 20 × 15 mm
      * Minimum wait time between one measurement and the start of the next: 20 ms (50 ms recommended)
    </td>
  </tr>
</table></div>

The HUSKYLENS module identifies traffic light colors to navigate around them on the correct side. This module was new to us, so we had to meticulously study its features and how to program it. The most appropriate mode for this challenge is color detection. However, 70% of the time it confused the pink of the parking lot with the red of the traffic lights, which caused serious programming issues. 

One major issue it caused was that it sometimes interfered with other robot components. For example, while it was connected, the 360-degree servo wouldn’t rotate properly and would jam, but when it was disconnected, the servo rotated more smoothly.

### The Team
The Minaguro team from Herencia, Spain, is made up of dedicated and hardworking members led by a teacher. This is our first year competing in the WRO Future Engineers category, and each member brings important skills to the team.

<br> **Miguel**
<br> **Age:** 17
<br> **Description:** Hi, I'm Miguel from Ciudad Real, Spain, and this is my first time participating in WRO Competition. I have always been into mechanics and robot building, so I didn't hesistate to take up this challenge. I am such a curious and competitive person, and I had put all my efforts in helping the team.

<br> **Natalia**
<br> **Age:** 17
<br> **Description:** Hi, I am Natalia, also from Ciudad Real, Spain, and it is my first time participating, too. I am really good at programming, which I actually enjoy doing. I am hardworking and creative, and this competition, despite being really demanding, has helped me to enter the engineering world.

<br> **Rocío** 
<br> **Age:** 16
<br> **Description:** Hi! I'm Rocío from Spain and this is the first time in the WRO competition. Since I was a kid, I've loved solving puzzles and maths problems. I started to interest in robotics when I was at secondary school, when my teacher taught us how to program. I thougth that was really fun.

<br> **Guillermo**
<br> **Age:** 16
<br> **Description:** Hi, I am Guillermo. I am from Ciudad Real, Spain, and I joined this project because I have always been really keen on I.T. and problem solving. Although this competition has been really challenging, the experience with all the team is worth it.


### Our Robot
Here are some pictures of our robot to help with it´s reproducibility:
<br> <img src="ROBOT/20260508_104557.jpg" alt="Imagen1" width="250" height="290">    **Robot´s Front View**
<br> <img src="ROBOT/20260508_104607.jpg" alt="Imagen2" width="250" height="290">    **Robot´s Upper View**
<br> <img src="ROBOT/20260508_104626.jpg" alt="Imagen3" width="250" height="290">    **Robot´s Right View**
<br> <img src="ROBOT/20260508_104641.jpg" alt="Imagen4" width="250" height="290">    **Robot´s Left View**
<br> <img src="ROBOT/20260508_104702.jpg" alt="Imagen5" width="250" height="290">    **Robot´s Back View**
<br> <img src="ROBOT/20260508_104720.jpg" alt="Imagen6" width="250" height="290">    **Robot´s Under View**

### Components used



### Software
Here are some programms we used to calibrate HCSR04 sensors and the steering servo:

* **[Calibrate HCSR04 sensors](PROGRAMS/HCSR04_x4_display.ino)**: Calibrate HCSR04 sensors
* **[Calibrate steering servo](11_JOYSTICK_CON_2_SERVOS.ino)**: Calibrate steering servo
* **[Calibrate drive servo](PROGRAMS/11_POTENCIOMETRO_CON_1_SERVO.ino)**: Calibrate drive servo </div>

Here is our final program:
* **[Final program](PROGRAMS/SEGUIDOR_V1_22.ino)**: Final program

### Our YouTube Channel
You can see how our robot works on our YouTube channel linked here: (<a href="https://www.youtube.com/@minagurowro2026">YouTube Channel link) </a>
