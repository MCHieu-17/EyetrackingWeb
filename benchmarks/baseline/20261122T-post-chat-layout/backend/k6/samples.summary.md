# k6 summary

scenario: samples

- http_req_waiting: p(95)=21.042, p(99)=25.847, avg=13.741, min=3.415, med=13.870, max=29.367, p(90)=20.420
- http_req_duration{expected_response:true}: p(90)=20.566, p(95)=21.111, p(99)=26.232, avg=13.891, min=3.478, med=13.973, max=29.664
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_blocked: med=0.011, max=0.136, p(90)=0.013, p(95)=0.015, p(99)=0.133, avg=0.014, min=0.002
- http_req_receiving: avg=0.109, min=0.021, med=0.077, max=0.601, p(90)=0.218, p(95)=0.248, p(99)=0.386
- http_req_connecting: med=0.000, max=0.097, p(90)=0.000, p(95)=0.000, p(99)=0.093, avg=0.002, min=0.000
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: p(90)=0.054, p(95)=0.061, p(99)=0.081, avg=0.041, min=0.006, med=0.042, max=0.128
- iterations: count=236.000, rate=23.131
- http_req_duration: p(99)=26.232, avg=13.891, min=3.478, med=13.973, max=29.664, p(90)=20.566, p(95)=21.111
