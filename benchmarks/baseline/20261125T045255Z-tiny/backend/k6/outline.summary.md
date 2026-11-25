# k6 summary

scenario: outline

- http_req_duration{expected_response:true}: min=1.820, med=8.171, max=59.808, p(90)=12.651, p(95)=13.372, p(99)=26.867, avg=8.485
- http_req_failed: rate=0.000
- http_req_duration: avg=8.485, min=1.820, med=8.171, max=59.808, p(90)=12.651, p(95)=13.372, p(99)=26.867
- vus: max=5.000, min=5.000
- http_req_connecting: p(95)=0.000, p(99)=0.256, avg=0.005, min=0.000, med=0.000, max=0.283, p(90)=0.000
- http_req_sending: avg=0.041, min=0.008, med=0.039, max=0.414, p(90)=0.053, p(95)=0.065, p(99)=0.151
- http_req_receiving: avg=0.141, min=0.010, med=0.121, max=0.831, p(90)=0.270, p(95)=0.359, p(99)=0.551
- iterations: count=242.000, rate=23.719
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_waiting: p(90)=12.354, p(95)=13.006, p(99)=26.611, avg=8.303, min=1.774, med=7.964, max=59.584
- http_req_blocked: p(95)=0.017, p(99)=0.301, avg=0.017, min=0.002, med=0.011, max=0.338, p(90)=0.013
