# k6 summary

scenario: samples

- http_req_failed: rate=0.000
- vus: max=5.000, min=5.000
- http_req_duration: p(90)=29.030, p(95)=31.864, p(99)=53.639, avg=19.099, min=6.589, med=16.460, max=55.924
- http_req_waiting: p(95)=31.730, p(99)=52.108, avg=18.863, min=6.435, med=16.177, max=55.707, p(90)=28.889
- http_req_sending: p(90)=0.050, p(95)=0.052, p(99)=0.074, avg=0.033, min=0.005, med=0.037, max=0.098
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: avg=0.011, min=0.002, med=0.010, max=0.119, p(90)=0.013, p(95)=0.014, p(99)=0.115
- http_req_duration{expected_response:true}: p(90)=29.030, p(95)=31.864, p(99)=53.639, avg=19.099, min=6.589, med=16.460, max=55.924
- http_req_connecting: p(95)=0.000, p(99)=0.084, avg=0.002, min=0.000, med=0.000, max=0.091, p(90)=0.000
- http_req_receiving: med=0.131, max=2.074, p(90)=0.429, p(95)=0.612, p(99)=1.059, avg=0.203, min=0.020
- iterations: count=230.000, rate=22.726
