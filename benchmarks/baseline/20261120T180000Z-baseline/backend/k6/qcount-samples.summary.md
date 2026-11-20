# k6 summary

scenario: samples

- http_req_waiting: med=24.150, max=51.857, p(90)=29.059, p(95)=31.421, p(99)=47.770, avg=24.106, min=11.262
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration{expected_response:true}: p(95)=31.637, p(99)=47.980, avg=24.270, min=11.374, med=24.335, max=52.066, p(90)=29.185
- http_req_blocked: p(95)=0.047, p(99)=0.183, avg=0.023, min=0.007, med=0.011, max=0.217, p(90)=0.017
- http_req_duration: min=11.374, med=24.335, max=52.066, p(90)=29.185, p(95)=31.637, p(99)=47.980, avg=24.270
- vus: max=1.000, min=1.000
- http_req_receiving: min=0.071, med=0.109, max=0.179, p(90)=0.174, p(95)=0.177, p(99)=0.179, avg=0.117
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.438
- http_req_connecting: max=0.159, p(90)=0.000, p(95)=0.008, p(99)=0.129, avg=0.008, min=0.000, med=0.000
- http_req_sending: p(90)=0.057, p(95)=0.082, p(99)=0.083, avg=0.047, min=0.028, med=0.042, max=0.083
