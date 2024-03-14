import asyncio
import serial_asyncio


async def main():
    reader, _ = await serial_asyncio.open_serial_connection(url='./reader', baudrate=115200)
    print('Reader created')
    # _, writer = await serial_asyncio.open_serial_connection(url='./writer', baudrate=115200)
    # print('Writer created')
    messages = [b'foo\n', b'bar\n', b'baz\n', b'qux\n']
    # sent = send(writer, messages)
    await recv(reader)
    # received = recv(reader)
    # await asyncio.wait([received])
    # await asyncio.wait([sent, received])


async def send(w, msgs):
    for msg in msgs:
        w.write(msg)
        print(f'sent: {msg.decode().rstrip()}')
        await asyncio.sleep(0.5)
    w.write(b'DONE\n')
    print('Done sending')


async def recv(r):
    while True:
        msg = await r.readuntil(b'\n')
        if msg.rstrip() == b'DONE':
            print('Done receiving')
            break
        print(f'received: {msg.rstrip().decode()}')

asyncio.run(main())

# loop = asyncio.get_event_loop()
# loop.run_until_complete(main(loop))
# loop.close()
