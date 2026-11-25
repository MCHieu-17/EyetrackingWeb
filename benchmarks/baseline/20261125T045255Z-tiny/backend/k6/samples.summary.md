# k6 summary

scenario: samples

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration: avg=14.189, min=3.502, med=15.376, max=23.628, p(90)=20.585, p(95)=21.186, p(99)=22.001
- http_req_blocked: avg=0.013, min=0.002, med=0.011, max=0.133, p(90)=0.013, p(95)=0.016, p(99)=0.128
- http_req_sending: p(95)=0.057, p(99)=0.098, avg=0.041, min=0.007, med=0.042, max=0.159, p(90)=0.051
- iterations: count=233.000, rate=23.179
- http_req_duration{expected_response:true}: p(99)=22.001, avg=14.189, min=3.502, med=15.376, max=23.628, p(90)=20.585, p(95)=21.186
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.101, p(90)=0.000, p(95)=0.000, p(99)=0.097
- http_req_receiving: p(95)=0.224, p(99)=0.300, avg=0.097, min=0.013, med=0.079, max=0.380, p(90)=0.189
- http_req_waiting: p(99)=21.844, avg=14.050, min=3.442, med=15.212, max=23.192, p(90)=20.476, p(95)=21.075
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
