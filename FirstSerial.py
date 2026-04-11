import serial
import struct

ser = serial.Serial(
    port='COM5',
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

print(f"Listening on {ser.port} at {ser.baudrate} baud...")

try:
    while True:
        flag = ser.read(1)

        if flag == b'\x55':  # 0x55 == 0b01010101
            tmp_bytes = ser.read(4)
            cou_bytes = ser.read(4)
            ppm_bytes = ser.read(4)
            hum_bytes = ser.read(4)
            # tmp==============================================
            if len(tmp_bytes) < 4:  # guard against timeout/incomplete read
                print("Incomplete read, skipping...")
                continue

            Tmp = struct.unpack('<f', tmp_bytes)[0]
            print(f"Tmp: {Tmp:.2f}")
            #==================================================
            #cou===============================================
            if len(cou_bytes) < 4:
                print("Incomplete read, skipping...")
                continue

            cou = struct.unpack('<f', cou_bytes)[0]
            print(f"cou: {cou:.2f}")
            #ppm==============================================
            if len(ppm_bytes) < 4:
                print("Incomplete read, skipping...")
                continue

            ppm = struct.unpack('<f', ppm_bytes)[0]
            print(f"ppm: {ppm:.2f}")
            #=================================================
            #hum==============================================
            if len(hum_bytes) < 4:
                print("Incomplete read, skipping...")
                continue

            hum = struct.unpack('<f', hum_bytes)[0]
            print(f"hum: {hum:.2f}")
           #==================================================
            print("---------------------")
           #==================================================
except KeyboardInterrupt:
    print("Stopped by user.")

finally:
    ser.close()
    print("Serial port closed.")
    #line de code dans gui 1114