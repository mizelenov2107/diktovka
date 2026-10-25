import json, time, sys, urllib.request
MODEL = sys.argv[1]
PROMPT = open(sys.argv[2]).read()
tests = [
 "ну короче слушай я сегодня короче не смогу на созвон в среду нет в четверг потому что у меня пара в вышке до шести вот давай типа перенесём на пятницу ну или на выходные как тебе удобно",
 "так значит смотри по задаче ну эластичность спроса это как бы отношение процентного изменения количества к процентному изменению цены и вот если она больше единицы значит спрос эластичный и выручка ну падает при росте цены короче",
 "в общем я подумал короче что надо сделать продукт типа кнопку которая печатает за тебя голосом ну как у того парня в рилсе и чтобы она ещё сокращала текст и писала нормальным русским языком а не как нейросеть блин вот",
]
for t in tests:
    body = json.dumps({"model": MODEL, "temperature": 0.2, "reasoning_effort": "none", "messages": [
        {"role": "system", "content": PROMPT}, {"role": "user", "content": t}]}).encode()
    r = urllib.request.Request("http://localhost:1234/v1/chat/completions", body, {"Content-Type": "application/json"})
    t0 = time.time(); out = json.load(urllib.request.urlopen(r, timeout=300))
    print(f"[{time.time()-t0:.1f} с] {out['choices'][0]['message']['content'].strip()}\n")
