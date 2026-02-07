volatile bool triggered = false;
volatile bool Trig_in_state = false;

volatile unsigned long echo_end_time = 0;
volatile bool data_ready = false;
unsigned long echo_start_time = 0;

void setup() {
  DDRD |= B00111000;  // Sets D3, D4, D5 outputs
  DDRB |= B00000100;  // Sets D10 as output
    
  PCICR |= (1 << PCIE0);    // enable PCMSK0 scan   
  PCMSK0 |= (1 << PCINT0);  // Set pin D8 (trigger pin) interrupt. 
  PCMSK0 |= (1 << PCINT1);  // Set pin D9 (echo in) interrupt.
  
  // Initialize Serial Communication for the Plotter
  Serial.begin(115200); 
}

void loop() {
  // CHECK FOR NEW DATA TO PLOT
  if (data_ready) {
    unsigned long duration = echo_end_time - echo_start_time;
    
    // Calculate distance in cm
    // Speed of sound = 343m/s = 0.0343 cm/us
    // Distance = (Time * Speed) / 2
    float distance = (duration / 2.0) * 0.0343;
    
    // Print to Serial (Plotter will graph this number)
    Serial.println(distance); 
    
    data_ready = false; // Reset flag
  }

  if(triggered) // Burst code starts...
  {
    delayMicroseconds(150);    
    
    // Enable Power to MAX232
    PORTD &= B11011111;   // D5 LOW
    
    // 8 Cycles of 40kHz burst
    for(int i=0; i<8; i++){
      PORTD |= B00001000;   // D3 HIGH
      PORTD &= B11101111;   // D4 LOW
      delayMicroseconds(12);
      PORTD &= B11110111;   // D3 LOW
      PORTD |= B00010000;   // D4 HIGH
      delayMicroseconds(12);
    }
   
    PORTD &= B11000111;   // D3, D4, D5 LOW (Finished burst)
    
    // START ECHO PULSE & RECORD TIME
    echo_start_time = micros(); // Save current time
    PORTB |= B00000100;         // Set D10 HIGH
    
    triggered = false;    // Reset the triggered value
  }
}

ISR(PCINT0_vect){
  if(PINB & B00000001){ 
    Trig_in_state = true; 
  }
  else if(Trig_in_state)
  {
    triggered = true;     
    Trig_in_state = false;    
  }

  // Check Echo Out Pin (D10) logic
  // Only stop the pulse if D10 is currently HIGH. 
  // This ensures we don't record timestamps during the Trigger phase.
  if (PORTB & B00000100) { 
     PORTB &= B11111011; // Set D10 LOW (End Echo)
     echo_end_time = micros(); // Record end time
     data_ready = true;  // Tell loop that data is ready
  }
}