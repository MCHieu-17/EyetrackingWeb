# k6 summary

scenario: replay

- http_req_waiting: p(90)=48.371, p(95)=49.075, p(99)=55.401, avg=33.679, min=12.917, med=34.699, max=56.983
- http_req_receiving: max=1.075, p(90)=0.293, p(95)=0.472, p(99)=0.954, avg=0.194, min=0.059, med=0.129
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.078, p(90)=0.000, p(95)=0.004, p(99)=0.063
- http_req_duration{expected_response:true}: p(95)=49.272, p(99)=55.586, avg=33.915, min=13.042, med=34.997, max=57.165, p(90)=48.531
- iterations: count=20.000, rate=4.259
- http_req_blocked: p(90)=0.016, p(95)=0.023, p(99)=0.097, avg=0.017, min=0.004, med=0.012, max=0.116
- http_req_failed: rate=0.000
- http_req_duration: max=57.165, p(90)=48.531, p(95)=49.272, p(99)=55.586, avg=33.915, min=13.042, med=34.997
- vus: min=1.000, max=1.000
- http_req_sending: max=0.058, p(90)=0.051, p(95)=0.055, p(99)=0.057, avg=0.042, min=0.012, med=0.045
