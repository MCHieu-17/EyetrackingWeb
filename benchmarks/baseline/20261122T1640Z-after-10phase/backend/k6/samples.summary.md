# k6 summary

scenario: samples

- http_req_sending: avg=0.039, min=0.008, med=0.039, max=0.426, p(90)=0.049, p(95)=0.052, p(99)=0.135
- http_req_waiting: min=5.484, med=19.174, max=61.926, p(90)=25.216, p(95)=26.979, p(99)=56.054, avg=18.232
- http_req_duration: p(95)=27.136, p(99)=56.155, avg=18.404, min=5.563, med=19.317, max=62.014, p(90)=25.394
- http_req_receiving: min=0.019, med=0.083, max=1.831, p(90)=0.237, p(95)=0.332, p(99)=0.716, avg=0.133
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration{expected_response:true}: avg=18.404, min=5.563, med=19.317, max=62.014, p(90)=25.394, p(95)=27.136, p(99)=56.155
- http_req_blocked: avg=0.012, min=0.002, med=0.011, max=0.125, p(90)=0.013, p(95)=0.015, p(99)=0.123
- http_req_failed: rate=0.000
- iterations: count=230.000, rate=22.550
- http_req_connecting: max=0.093, p(90)=0.000, p(95)=0.000, p(99)=0.087, avg=0.002, min=0.000, med=0.000
- vus: min=5.000, max=5.000
