# k6 summary

scenario: aoi_summary

- http_req_duration{expected_response:true}: avg=21.973, min=9.822, med=19.208, max=52.100, p(90)=33.048, p(95)=35.558, p(99)=51.994
- iterations: count=90.000, rate=8.973
- http_req_duration: avg=21.973, min=9.822, med=19.208, max=52.100, p(90)=33.048, p(95)=35.558, p(99)=51.994
- http_req_waiting: med=19.047, max=52.002, p(90)=32.922, p(95)=35.371, p(99)=51.871, avg=21.845, min=9.762
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_connecting: p(99)=0.129, avg=0.003, min=0.000, med=0.000, max=0.149, p(90)=0.000, p(95)=0.000
- http_req_blocked: max=0.226, p(90)=0.015, p(95)=0.021, p(99)=0.170, avg=0.016, min=0.004, med=0.011
- http_req_receiving: max=0.175, p(90)=0.098, p(95)=0.137, p(99)=0.170, avg=0.069, min=0.028, med=0.062
- http_req_sending: min=0.016, med=0.054, max=0.175, p(90)=0.077, p(95)=0.097, p(99)=0.155, avg=0.059
- http_req_failed: rate=0.000
- vus: min=2.000, max=2.000
